# core

Shared code that modules use: config, database, logs, HTTP hooks, Discord and RunPod clients, jobs, tools, audit and org secrets. `core/` imports nothing from `modules/`; the import-linter contract `core imports no module` in `pyproject.toml` checks it.

## Files

| File | Holds |
| --- | --- |
| `config.py` | `Config` and the `config` instance: settings from `.env` and the environment |
| `db/` | `Base` (`base.py`), `DBConnect`, the `db_connect` instance and `session()` (`session.py`) |
| `errors.py`, `time.py` | `ServiceError`, the error a service raises with an HTTP status; `utcnow()` and `iso()` for naive UTC times |
| `jobs.py` | `@job` and `defer()`: Procrastinate on Postgres, threads on SQLite |
| `tools.py` | The `@tool` registry (`TOOLS`, `ToolSpec`, `ToolError`) |
| `audit.py` | The `audit_log` table, `record()` and the `audit.prune` job |
| `secrets.py` | The `org_secrets` table, `declare()`, `set_secret` and `get_secret`, encrypted with `SECRETS_KEY` |
| `log.py` | `get_logger`, JSON log lines and `init_sentry` |
| `http/` | `responses.py` (`json_body`, `error`, `error_handler`), `request_log.py` (one line for each request, `bearer_token()`), `audit_hook.py` (writes successful changes to the audit log) |
| `integrations/` | `discord.py` (`DiscordDirectory`, messages and reactions over Discord's REST API) and `runpod.py` (RunPod REST client) |

## Surface

- Jobs: `audit.prune`, schedule `30 3 * * *`, keeps `AUDIT_RETENTION_DAYS` (default 365).
- Tables: `audit_log`, `org_secrets`.

See [docs/architecture.md](../docs/architecture.md).
