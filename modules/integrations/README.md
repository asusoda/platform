# integrations

Gives agents the tools of the services an org connects on the Integrations page, through the same token and MCP server as the Platform tools. Platform passes each call to the service's own MCP server with the org's saved keys. The agent never gets the keys.

## Files

| File | Holds |
| --- | --- |
| `servers.py` | The MCP server of each service: URL, sign-in with the org's keys, scopes, and the repo a call acts on; declares the `github:*` scopes and token limits |
| `service.py` | The tools a token may see and the call to the remote server: scope, confirm, tool name and repo limits |
| `mcp_client.py` | A small MCP client over streamable HTTP |

## Surface

- Routes: none. The tools are served by the mcp module at `/mcp` and `/api/tools`.
- Jobs: none.
- Tools: `github.*`, the tools that the GitHub MCP server lists. `github:read` gives the read-only tools; `github:write` gives the others, which run only with `confirm=true`.
- Tables: none. Token limits are the `limits` column of `machine_tokens`.

See [docs/integrations.md](../../docs/integrations.md#tools-for-agents).
