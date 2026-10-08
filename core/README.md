# core

Shared code the modules build on: configuration, database, logging, tokens, Discord REST access, jobs, tools, audit and org secrets.

## Files

| File | Holds |
| --- | --- |
| `TokenManager.py` | `TokenManager`: RS256 keys in `./data`, access and refresh token pairs, app tokens, revocation, refresh token cleanup |
| `audit.py` | The `audit_log` table, `record()`, and the `audit.prune` job (cron `30 3 * * *`, `AUDIT_RETENTION_DAYS`) |
| `audit_http.py` | After-request hook that records successful API writes in the audit log |
| `base.py` | The SQLAlchemy declarative `Base` |
| `clerk_auth.py` | Clerk client and `verify_clerk_token` |
| `config.py` | `Config`: settings from `.env` and the environment |
| `db.py` | `DBConnect`: engine, sessions, `get_db`, and user, point and storefront query helpers |
| `discord_directory.py` | `DiscordDirectory`: guilds, roles and members over Discord's REST API with the bot token, cached |
| `discord_messages.py` | Sends messages and reactions over Discord's REST API without the gateway bot |
| `errors.py` | `ServiceError`, the error services raise with an HTTP status |
| `jobs.py` | `@job` and `defer()`: Procrastinate on Postgres (run by `worker_main.py`), threads on SQLite |
| `logging_config.py` | Logger setup, JSON formatting of request and access lines, `get_logger` |
| `request_log.py` | One log line per API request: route, org, credential kind, origin |
| `runpod.py` | RunPod REST client; each org's key is the org secret `runpod_api_key` |
| `secrets.py` | The `org_secrets` table, `declare()`, and Fernet-encrypted `set_secret` and `get_secret` keyed by `SECRETS_KEY` |
| `tools.py` | The `@tool` registry (`TOOLS`, `ToolSpec`, `ToolError`) served over MCP and `/api/tools` |
| `types.py` | `ExtendedRequest`, a typed Flask request; nothing imports it |

## Rule

core imports nothing from `modules/`. The import-linter contract `core imports no module` in `[tool.importlinter]` of `pyproject.toml` enforces it (`make check` runs `lint-imports`), with three listed exceptions: `core.db -> modules.storefront.models`, `core.TokenManager -> modules.auth.models`, `core.discord_directory -> modules.organizations.models`.

## More

[docs/02-architecture.md](../docs/02-architecture.md)
