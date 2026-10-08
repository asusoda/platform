# Tools and the MCP server

Apps and agents read platform data through tools. The same tools are served two ways:

- over MCP (streamable HTTP) by `mcp_main.py`, at `:8001/mcp`
- over plain HTTP by the API: `GET /api/tools` lists them, `POST /api/tools/<name>` calls one with the
  arguments as the JSON body

Both take a machine token (`Authorization: Bearer plat_...`, see
[Authentication](./04-authentication.md#machine-tokens-apps-agents-clis)). Each request sees only the
tools whose scope the token holds and whose module is on for the token's org. An unknown tool and a
tool the token may not use both return 404 (`isError` over MCP), so a token cannot probe for tools.

## Tools today

| Tool | Scope | Module | Returns |
|------|-------|--------|---------|
| `org.info` | `org:read` | | Name, prefix, description, module switches |
| `events.list` | `calendar:read` | calendar | Upcoming events from the org's Notion calendar |
| `points.leaderboard` | `points:read` | points | Top members by points, names and totals only. Argument `limit` (1 to 100, default 10) |

All are read-only.

## Adding a tool

1. Put the logic in the module's `service.py` (no Flask; checked by `lint-imports`).
2. Declare the scope in that module: `modules.auth.scopes.declare("x:read", "...")`.
3. In the module's `tools.py`:

   ```python
   from core.tools import ToolError, tool

   @tool("x.list", description="...", scope="x:read", module="x",
         input_schema={"type": "object", "properties": {...}, "additionalProperties": False})
   def x_list(db, org, caller, **arguments):
       return {...}  # JSON-ready
   ```

4. Add the file to `TOOL_MODULES` in `modules/registry.py`.

Arguments are checked against `input_schema` before the function runs. Raise `ToolError(message,
status)` to refuse. The function always gets the caller's own org; tools never take an org argument.

## Audit

Every call, allowed or refused, is a row in `audit_log`: `action=tool <name>`, `source=mcp` or `api`,
the org, `actor_id=<kind>:<name>#<token id>`, the status and the duration.

## Running it

`docker compose --profile mcp up -d mcp`. It reads the same `.env` and database as the API and can
run as several processes, since it keeps no session state (stateless streamable HTTP, JSON
responses). Connect a client with the URL `http://<host>:8001/mcp` and the header
`Authorization: Bearer plat_...`.
