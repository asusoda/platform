# mcp

Serves the tools other modules register to apps and agents that hold a machine token: over MCP streamable HTTP at `/mcp` and as plain HTTP at `/api/tools`. A caller sees only the tools its token scopes and its org's module switches allow.

## Files

| File | Holds |
| --- | --- |
| `server.py` | The MCP server app (`build_app`), run by `mcp_main.py` |
| `runtime.py` | Lists and calls tools for a machine caller: scope, module switch and input schema checks; records each call in the audit log |
| `api.py` | The HTTP mirror: `GET /api/tools` lists tools, `POST /api/tools/<name>` calls one |

## Surface

- Routes: `/api/tools`, no module switch; machine token required. A tool with a `module` is hidden when that module is off for the caller's org.
- Jobs: none.
- Tools: none of its own; it serves `core.tools.TOOLS`, filled by the modules in `TOOL_MODULES` in `modules/registry.py`.
- Tables: none.

## More

[docs/tools-and-mcp.md](../../docs/tools-and-mcp.md)
