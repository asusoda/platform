# core

Shared code the modules build on: configuration, database, logging, HTTP hooks, Discord and RunPod clients, jobs, tools, audit and org secrets.

## Files

| File | Holds |
| --- | --- |
| `audit.py` | The `audit_log` table, `record()`, and the `audit.prune` job (cron `30 3 * * *`, `AUDIT_RETENTION_DAYS`) |
| `config.py` | `Config` and the `config` instance: settings from `.env` and the environment |
| `db/` | `Base`, `DBConnect`, the `db_connect` instance, `session()`, and storefront query helpers |
| `errors.py` | `ServiceError`, the error services raise with an HTTP status |
| `http/audit_hook.py` | After-request hook that records successful API writes in the audit log |
| `http/request_log.py` | One log line per API request: route, org, credential kind, origin |
| `integrations/discord.py` | `DiscordDirectory` (guilds, roles and members, cached), `send_message` and `add_reaction`, over Discord's REST API with the bot token |
| `integrations/runpod.py` | RunPod REST client; each org's key is the org secret `runpod_api_key` |
| `jobs.py` | `@job` and `defer()`: Procrastinate on Postgres (run by `worker_main.py`), threads on SQLite |
| `log.py` | Logger setup, JSON formatting of request and access lines, `get_logger`, `init_sentry` |
| `secrets.py` | The `org_secrets` table, `declare()`, and Fernet-encrypted `set_secret` and `get_secret` keyed by `SECRETS_KEY` |
| `time.py` | `utcnow()` and `iso()`: naive UTC datetimes as the database stores them |
| `tools.py` | The `@tool` registry (`TOOLS`, `ToolSpec`, `ToolError`) served over MCP and `/api/tools` |

## Rule

core imports nothing from `modules/`. The import-linter contract `core imports no module` in `[tool.importlinter]` of `pyproject.toml` enforces it (`make check` runs `lint-imports`), with one listed exception: `core.db.session -> modules.storefront.models`.

## More

[docs/02-architecture.md](../docs/02-architecture.md)
