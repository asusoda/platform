"""The MCP server of an app, reached through Platform: list its tools and call one. No Flask here.

An app names its server in its manifest: mcp.url, or mcp.port and mcp.path on its RunPod pod. mcp.token_secret
names the org secret sent as the bearer token. Only public https addresses are reached.
"""

from __future__ import annotations

import json
from typing import Any

import anyio
import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from core import hosting, net, secrets
from core.log import get_logger
from modules.runpod.models import App
from modules.runpod.service import AppError, _find, _manifest

logger = get_logger(__name__)

#: Seconds one list or call may take, connection included.
TIMEOUT_SECONDS = 60
#: Characters of a tool result handed back.
MAX_RESULT_CHARS = 20_000


def endpoint(app: App) -> str:
    """The URL of the app's MCP server."""
    spec = _manifest(app).get("mcp")
    if not isinstance(spec, dict):
        raise AppError("The app names no MCP server. Add mcp to its manifest", 404)
    if spec.get("url"):
        return str(spec["url"])
    if str(app.provider) != hosting.DEFAULT or not app.pod_id:
        raise AppError("The app is not on a RunPod pod yet. Give mcp.url in its manifest", 409)
    return f"https://{app.pod_id}-{spec['port']}.proxy.runpod.net{spec.get('path') or '/mcp'}"


def _token(db, org_id: int | None, app: App) -> str | None:
    name = (_manifest(app).get("mcp") or {}).get("token_secret")
    if not name:
        return None
    value = secrets.get_deployment_secret(db, name) if org_id is None else secrets.get_secret(db, org_id, name)
    if not value:
        raise AppError(f"Set the secret {name} to the app's MCP token on the Secrets page", 503)
    return value


async def _session(url: str, token: str | None, work):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with anyio.fail_after(TIMEOUT_SECONDS):
        async with httpx2.AsyncClient(headers=headers, timeout=TIMEOUT_SECONDS) as client:
            async with streamable_http_client(url, http_client=client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await work(session)


def _run(db, org_id: int | None, name: str, work) -> Any:
    app = _find(db, org_id, name)
    url = endpoint(app)
    try:
        net.check_public(url)
    except net.NotPublic as e:
        raise AppError(str(e)) from e
    token = _token(db, org_id, app)
    try:
        return anyio.run(_session, url, token, work)
    except TimeoutError as e:
        raise AppError(f"The MCP server of {name} did not answer within {TIMEOUT_SECONDS} seconds", 504) from e
    except Exception as e:  # The SDK raises its own and httpx2 errors; each one means the server failed
        logger.warning("MCP server of app %s failed: %s", name, type(e).__name__)
        raise AppError(f"The MCP server of {name} failed: {_reason(e)}", 502) from e


def _reason(error: BaseException) -> str:
    inner = getattr(error, "exceptions", None)
    if inner:
        return _reason(inner[0])
    text = str(error) or type(error).__name__
    return text[:300]


def list_tools(db, org_id: int | None, name: str) -> list[dict]:
    """The tools the app's MCP server lists: name, description and input schema."""

    async def work(session: ClientSession):
        listed = await session.list_tools()
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.input_schema} for t in listed.tools
        ]

    return _run(db, org_id, name, work)


def call_tool(db, org_id: int | None, name: str, tool: str, arguments: dict | None) -> dict:
    """One call of a tool on the app's MCP server: its text, structured result, and whether it failed."""

    async def work(session: ClientSession):
        result = await session.call_tool(tool, arguments or {})
        parts = [getattr(c, "text", None) or json.dumps(c.model_dump(mode="json")) for c in result.content]
        text = "\n".join(parts)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n[result cut]"
        return {"text": text, "structured": result.structured_content, "is_error": bool(result.is_error)}

    return _run(db, org_id, name, work)
