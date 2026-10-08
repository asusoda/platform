"""Tools that apps and agents call over MCP and over HTTP (/api/tools).

A module declares tools in its tools.py with @tool. A tool function receives a database session,
the caller's organization, the caller, and the validated arguments, and returns JSON-ready data.
The runtime that checks tokens, scopes and module switches is modules/mcp/runtime.py.
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


TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, *, description: str, scope: str, module: str | None = None, input_schema: dict | None = None):
    """Register a tool. The function is called as func(db, org, caller, **arguments)."""

    def register(func: Callable[..., Any]) -> Callable[..., Any]:
        schema = input_schema or {"type": "object", "properties": {}}
        TOOLS[name] = ToolSpec(name, description, scope, func, module, schema)
        return func

    return register
