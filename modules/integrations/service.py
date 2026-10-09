"""Tools of connected services, passed through to their MCP servers for machine tokens. No Flask here.

A token with a server's read scope sees the tools the server marks read-only; its write scope adds the
others, which run only with confirm=true. Token limits narrow the tools by name pattern and the repos a
call may act on. With a repo limit, only tools that name one repo are shown. The tool list of each org is
cached for CACHE_SECONDS. Every call goes through modules/mcp/runtime.py, which audits it.
"""

import fnmatch
import time
from functools import partial
from typing import Any

from core.integrations import registry
from core.log import get_logger
from core.tools import CONFIRM_NOTE, ToolError, ToolSpec
from modules.auth.machine_tokens import MachineCaller
from modules.integrations import mcp_client
from modules.integrations.servers import SERVERS, RemoteServer

logger = get_logger(__name__)

CACHE_SECONDS = 600
MAX_RESULT_CHARS = 100_000

for _server in SERVERS.values():
    registry.use(_server.integration, "integrations")

_cache: dict[tuple[str, int], tuple[float, list[dict]]] = {}


def _remote_tools(db, server: RemoteServer, org_id: int) -> list[dict]:
    """The server's tools for the org, cached. Empty when the org has no keys or the server fails."""
    headers = server.headers(db, org_id)
    if headers is None:
        return []
    cached = _cache.get((server.key, org_id))
    if cached is not None and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        tools = mcp_client.list_tools(server.url(), headers)
    except mcp_client.RemoteError as e:
        logger.warning("remote tool list failed server=%s org=%s reason=%s", server.key, org_id, e)
        return []
    _cache[(server.key, org_id)] = (time.monotonic(), tools)
    return tools


def clear_cache() -> None:
    _cache.clear()


def _read_only(tool: dict) -> bool:
    annotations = tool.get("annotations")
    return isinstance(annotations, dict) and annotations.get("readOnlyHint") is True


def _takes_target(server: RemoteServer, tool: dict) -> bool:
    schema = tool.get("inputSchema")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    probe = dict.fromkeys(properties, "x") if isinstance(properties, dict) else {}
    return server.target(probe) is not None


def _allowed_target(patterns: list[str], target: str) -> bool:
    return any(fnmatch.fnmatchcase(target, pattern) for pattern in patterns)


def _spec(server: RemoteServer, tool: dict, write: bool) -> ToolSpec:
    name = f"{server.key}.{tool['name']}"
    given = tool.get("inputSchema")
    schema: dict[str, Any] = dict(given) if isinstance(given, dict) else {"type": "object"}
    description = str(tool.get("description") or "")[:2000]
    if write:
        schema["properties"] = {**(schema.get("properties") or {}), "confirm": {"type": "boolean"}}
        description += CONFIRM_NOTE
    return ToolSpec(
        name=name,
        description=description,
        scope=server.write_scope if write else server.read_scope,
        func=partial(_call, server, str(tool["name"])),
        input_schema=schema,
        confirm=write,
        integration=server.integration,
    )


def tools_for(db, org_id: int, caller: MachineCaller) -> list[ToolSpec]:
    """The remote tools this token may see."""
    found = []
    for server in SERVERS.values():
        can_read, can_write = caller.allows(server.read_scope), caller.allows(server.write_scope)
        if not (can_read or can_write):
            continue
        name_limits = caller.limit(server.key, "tools")
        target_limits = caller.limit(server.key, server.target_limit) if server.target_limit else None
        for tool in _remote_tools(db, server, org_id):
            write = not _read_only(tool)
            if (write and not can_write) or (not write and not can_read):
                continue
            name = f"{server.key}.{tool['name']}"
            if name_limits is not None and not any(fnmatch.fnmatchcase(name, p) for p in name_limits):
                continue
            if target_limits is not None and not _takes_target(server, tool):
                continue
            found.append(_spec(server, tool, write))
    return found


def find(db, org_id: int, caller: MachineCaller, name: str) -> ToolSpec | None:
    if "." not in name or name.split(".", 1)[0] not in SERVERS:
        return None
    return next((spec for spec in tools_for(db, org_id, caller) if spec.name == name), None)


def _text(result: dict) -> str:
    parts = [c.get("text", "") for c in result.get("content") or [] if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(p for p in parts if isinstance(p, str))


def _call(server: RemoteServer, tool_name: str, db, org, caller: MachineCaller, **arguments: Any) -> Any:
    target_limits = caller.limit(server.key, server.target_limit) if server.target_limit else None
    if target_limits is not None:
        target = server.target(arguments)
        if target is None or not _allowed_target(target_limits, target):
            raise ToolError(f"This token may not act on {target or 'that target'}", 403)
    headers = server.headers(db, int(org.id))
    if headers is None:
        raise ToolError(f"Connect {server.key} on the Integrations page first", 409)
    try:
        result = mcp_client.call_tool(server.url(), headers, tool_name, arguments)
    except mcp_client.RemoteError as e:
        raise ToolError(f"{server.key}: {e}", e.status) from e
    text = _text(result)
    if result.get("isError") is True:
        raise ToolError(f"{server.key}: {text[:1000] or 'the tool failed'}", 422)
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    return {"text": text[:MAX_RESULT_CHARS], "truncated": len(text) > MAX_RESULT_CHARS}
