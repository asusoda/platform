# Architecture

Platform is a Flask API with a Discord bot, a job worker and an MCP server. All four use the same code in `core/` and `modules/` and the same database.

## Processes

| Process | Entry point | Port | Use |
| --- | --- | --- | --- |
| API | `main.py` under gunicorn | 8000 | Every HTTP route |
| Discord bot | `bot_main.py` | | Slash commands and Jeopardy, with the cogs in `modules/bot`, `modules/games` and `modules/leetcode` |
| Job worker | `worker_main.py` | | Runs jobs from the Procrastinate queue. Postgres only |
| MCP server | `mcp_main.py` | 8001 | Module tools for agents, over MCP |
| Dashboard | `dashboard/` | 5000 (5173 in dev) | The officer pages for each org and the member store (Vite, React) |

The database is Postgres in production, or SQLite for a small deployment. Alembic makes the schema.

The API does not need the bot. It reads Discord servers, roles and members over Discord's REST API with `BOT_TOKEN` (`core/integrations/discord.py`). The Jeopardy routes under `/api/bot` are the exception: they call the bot's cogs, so they work only when the bot runs in the API process (`RUN_BOT_IN_API=true`).

## Layout

```
main.py, bot_main.py, worker_main.py, mcp_main.py   the four entry points
core/          shared code: config, database, jobs, tools, secrets, audit, logs, HTTP hooks, Discord and RunPod clients
modules/       one folder per module, not nested; registry.py mounts the blueprints, manifest.py lists categories, models, jobs and tools
alembic/       migrations
tests/         pytest; tests/contract/ checks every route a client uses
web/, dashboard/, site/   the web app, the officer dashboard, the docs and landing site
deploy/        the RunPod start script, the Hermes image and the SQLite to Postgres copy script
```

`core/` imports nothing from `modules/`. Only the route files (`api.py`, `member_api.py`), `registry.py`, `cli.py` and the route helpers in `modules/auth/` import Flask. `make ci` checks both with import-linter.

## How a request runs

1. Flask-CORS adds the CORS headers for an allowed origin. The list is in `main.py`, plus `CORS_EXTRA_ORIGINS` and `DASHBOARD_URL`.
2. If the path starts with a `DISABLED_ROUTES` prefix, the API returns 404.
3. `modules/registry.py` sends the request to the module blueprint. If the module is turned off for the org in the URL, it returns 404.
4. A decorator from `modules/auth` checks the caller. See [Authentication](./authentication.md).
5. The view reads the request, calls the module's `service.py` and returns JSON.
6. Before the response goes out, `core/http/request_log.py` logs one line, and `core/http/audit_hook.py` writes each successful change to `audit_log`.

The org comes from the URL (`org_prefix` or `org_id`), or from the machine token. The `X-Organization-*` headers that older clients send are used only in the request log.

Views get a database session from `officer_route`, `machine_route` or `member_view` in `modules/auth/routes.py`, or from `core.db.session()`. Older views call `next(db_connect.get_db())` and close the session in a `finally` block.

## Modules

A module is a folder in `modules/` with only the files it needs: `service.py` for the logic, `api.py` for the routes, `models.py`, `jobs.py` and `tools.py`. The REST routes, jobs, tools and the bot call the same `service.py` functions. [Writing a module](./writing-a-module.md) gives the rules and the places to register a module.

Orgs can turn off the optional modules: `points`, `storefront`, `calendar`, `leetcode`, `compute` and `alerts`. The list is `OPTIONAL_MODULES` in `modules/organizations/service.py`. The switches are in `Organization.config["modules"]`. A module with no entry is on. Officers set the switches on the dashboard Settings page or with `flask --app main org modules <prefix> --on x --off y`.

## Jobs

A module declares a job in its `jobs.py` with `@job(name, cron=..., retry=...)` from `core/jobs.py`. Code starts a job with `jobs.defer(name, **kwargs)`. Each module README lists its jobs. `flask --app main jobs list` lists all of them.

- On Postgres, `defer` adds a row to the Procrastinate queue. The worker runs the job, tries it again if it fails, and runs the periodic jobs.
- On SQLite, there is no queue. `defer` runs the job in a thread of the calling process. A thread in the API runs the periodic jobs, and `worker_main.py` stops.

`JOBS_BACKEND=inline|procrastinate` sets the choice. The tests use `inline`. Each run of a job with `audit=True` (the default) is written to `audit_log`.

## Tools and the MCP server

Apps and agents read and change Platform data through tools. A module declares a tool in its `tools.py` with `@tool` from `core/tools.py`. Platform serves each tool two ways:

- Over MCP (streamable HTTP) from `mcp_main.py`, at `http://<host>:8001/mcp`.
- Over HTTP from the API: `GET /api/tools` lists the tools, and `POST /api/tools/<name>` calls one with the arguments as the JSON body.

Both need a machine token: `Authorization: Bearer plat_...`. A caller sees only the tools that its token scopes allow and that its org has turned on. An unknown tool and a refused tool both return 404, so a token cannot find tools it may not use. A tool always acts on the caller's org. It has no org argument.

| Tool | Scope | Module |
| --- | --- | --- |
| `org.info` | `org:read` | organizations |
| `events.list` | `calendar:read` | calendar |
| `points.leaderboard` | `points:read` | points |
| `knowledge.search` | `knowledge:read` | knowledge |
| `asu.query` | `knowledge:read` | asu |
| `apps.list` | `apps:read` | runpod |

Each call, allowed or refused, is a row in `audit_log` with `action=tool <name>` and `source=mcp` or `api`. The MCP server keeps no session state, so you can run more than one. Start it with `docker compose --profile mcp up -d mcp`.

## Outside services

| Service | Use | Code |
| --- | --- | --- |
| Discord | Sign-in, role and member checks, the bot | `core/integrations/discord.py`, `modules/auth`, `modules/bot` |
| Clerk | Member sign-in on the public website storefront | `modules/auth/clerk.py` |
| Notion, Google Calendar | Calendar sync | `modules/calendar/clients/` |
| RunPod | Compute pods and app deploys | `core/integrations/runpod.py` |
| LeetCode GraphQL | The daily question and solve checks | `modules/leetcode/client.py` |
| Sentry | Errors, logs and traces, if `SENTRY_DSN` is set | `core/log.py` |
