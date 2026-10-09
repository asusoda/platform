"""The MCP server: the same tools as /api/tools, over MCP streamable HTTP at /mcp.

Every request carries a machine token (Authorization: Bearer plat_...). The tool list is built
per request from that token, so a client sees only the tools its scopes and its org's modules allow.
"""

import json

from anyio import to_thread
from mcp import types
from mcp.server.lowlevel import Server

from core.db import db_connect
from core.tools import ToolError
from modules.auth import machine_tokens
from modules.mcp import runtime


class Unauthorized(Exception):
    pass


def _token(ctx) -> str | None:
    request = getattr(ctx, "request", None)
    header = request.headers.get("authorization", "") if request is not None else ""
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def _list(token: str | None) -> list[types.Tool]:
    db = db_connect.SessionLocal()
    try:
        caller = machine_tokens.verify(db, token)
        if caller is None:
            raise Unauthorized("A valid machine token is required")
        return [
            types.Tool(
                name=spec.name,
                description=spec.description,
                input_schema=spec.input_schema,
                annotations=types.ToolAnnotations(read_only_hint=spec.read_only, destructive_hint=spec.confirm),
            )
            for spec in runtime.available(db, caller)
        ]
    finally:
        db.close()


def _call(token: str | None, name: str, arguments: dict | None) -> types.CallToolResult:
    db = db_connect.SessionLocal()
    try:
        caller = machine_tokens.verify(db, token)
        if caller is None:
            return _error("A valid machine token is required")
        try:
            result = runtime.call(db, caller, name, arguments, source="mcp")
        except ToolError as e:
            return _error(e.message)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, default=str))],
            structured_content=result if isinstance(result, dict) else {"result": result},
        )
    finally:
        db.close()


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


async def on_list_tools(ctx, params) -> types.ListToolsResult:
    tools = await to_thread.run_sync(_list, _token(ctx))
    return types.ListToolsResult(tools=tools)


async def on_call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    return await to_thread.run_sync(_call, _token(ctx), params.name, params.arguments)


def build_server() -> Server:
    return Server(
        "platform",
        instructions="Tools over this organization's platform data. Each token sees only its own org.",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


def build_app(host: str = "0.0.0.0"):  # nosec B104 - the container binds all interfaces, as main.py does
    """The ASGI app. Stateless JSON responses, so any number of processes can serve it."""
    return build_server().streamable_http_app(stateless_http=True, json_response=True, host=host)
