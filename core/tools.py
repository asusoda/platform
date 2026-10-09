"""Tools that apps and agents call over MCP and over HTTP (/api/tools).

A module declares tools in its tools.py with @tool. A tool function receives a database session,
the caller's organization, the caller, and the validated arguments, and returns JSON-ready data.
The runtime that checks tokens, scopes and module switches is modules/mcp/runtime.py.

A tool made with confirm=True changes or deletes something that is hard to undo. It takes a boolean argument
confirm. Without confirm=true the runtime does not run it and returns what the call would do.

A tool made with integration calls that connected service. The Tokens page lists it under the integration.
A tool made with available is shown only to orgs for which available(db, org_id) is true, such as orgs that
saved their own keys for the service.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.errors import ServiceError


class ToolError(ServiceError):
    """A tool refused or failed. status follows HTTP: 400 bad arguments, 404 not found, and so on."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    scope: str
    func: Callable[..., Any]
    module: str | None = None  # optional module that must be on for the caller's org
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    confirm: bool = False  # the call runs only with confirm=true
    preview: Callable[..., Any] | None = None  # called like func when confirm is missing; it must change nothing
    integration: str | None = None  # the connected service the tool calls
    available: Callable[[Any, int], bool] | None = None  # the org can use the tool now

    @property
    def read_only(self) -> bool:
        """A tool behind a read scope changes nothing."""
        return self.scope.endswith(":read")


TOOLS: dict[str, ToolSpec] = {}


CONFIRM_NOTE = " Runs only with confirm=true; without it the result says what the call would do."


def tool(
    name: str,
    *,
    description: str,
    scope: str,
    module: str | None = None,
    input_schema: dict | None = None,
    confirm: bool = False,
    preview: Callable[..., Any] | None = None,
    integration: str | None = None,
    available: Callable[[Any, int], bool] | None = None,
):
    """Register a tool. The function is called as func(db, org, caller, **arguments), without confirm."""

    def register(func: Callable[..., Any]) -> Callable[..., Any]:
        schema: dict[str, Any] = input_schema or {"type": "object", "properties": {}}
        text = description
        if confirm:
            current = schema.get("properties")
            properties: dict[str, Any] = {**current} if isinstance(current, dict) else {}
            properties["confirm"] = {"type": "boolean"}
            schema = {**schema, "properties": properties}
            text += CONFIRM_NOTE
        TOOLS[name] = ToolSpec(name, text, scope, func, module, schema, confirm, preview, integration, available)
        return func

    return register
