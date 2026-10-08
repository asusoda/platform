# 2. Architecture

## The two containers

```
┌──────────────────────────────┐        ┌──────────────────────────────┐
│  soda-web       :5000        │        │  soda-internal-api  :8000    │
│  node:18-alpine              │──HTTP─▶│  python:3.12-slim            │
│  `serve -s build`            │        │  gunicorn main:app           │
│  Static React bundle         │        │  Flask API                   │
└──────────────────────────────┘        └──────────────┬───────────────┘
                                                        │
                                       ┌────────────────┼─────────────────┐
                                       ▼                ▼                 ▼
                                  ./data/user.db    Discord API     Notion + Google
                                    (SQLite)          (gateway)       Calendar APIs
```

Both are defined in `docker-compose.yml`. They share a bridge network `soda-network`. The web
container has no server-side logic — it is a static bundle served by `serve`, and it talks to the
API over the public internet (or `localhost` in dev) using `REACT_APP_API_URL`, which is baked in
at **build time**.

The database is a **single SQLite file** at `./data/user.db`, bind-mounted from the host. There is
no database server. This is a real constraint: SQLite handles one writer at a time, so heavy
concurrent writes will block.

In production a third container, `soda-bot`, runs `bot_main.py`: the Discord bot, from the same
image. The API reads Discord through the REST API (`core/discord_directory.py`) and does
not need the bot. The sections below describe `python3 main.py`, which still starts the bot in a
thread for local development unless `RUN_BOT_IN_API=false`.

## What runs inside the API container

`main.py` is the entry point. When you run `python3 main.py`, this happens:

```
main.py imported
 └─ imports shared.py  ─────────────────────────────────────────────┐
    ├─ builds the Flask `app` (static folder points at web/build)   │
    ├─ configures CORS (allowlist of 6 origins)                     │
    ├─ builds `config` (Config, reads .env)                         │  All of this happens
    ├─ initialises Sentry if SENTRY_DSN is set                      │  at import time, as a
    ├─ builds `db_connect` (DBConnect → sqlite:///./data/user.db)   │  side effect. There is
    │   └─ creates ./data/, creates all tables                      │  no app factory.
    ├─ builds `tokenManager` (loads or generates RSA keypair)       │
    ├─ Base.metadata.create_all()                                   │
    ├─ builds the Notion client                                     │
    └─ builds a BotFork instance (see gotcha: this one is unused)   ┘

 └─ imports every module's blueprint
 └─ creates MultiOrgCalendarService, attaches to app.multi_org_calendar_service
 └─ registers 9 blueprints under /api/*
 └─ defines GET /health

main.py `initialize_app()` (only when run as __main__)
 ├─ starts daemon thread "AuthBotThread"
 │   └─ new asyncio event loop
 │       └─ create_auth_bot(loop) → BotFork with HelperCog, GameCog, LeetCodeCog
 │           └─ attached to app.auth_bot   ← this is the instance everything uses
 │           └─ bot.start(BOT_TOKEN) blocks this thread forever
 └─ app.run(host=0.0.0.0, port=8000, debug=not IS_PROD)
```

### Threads at runtime

| Thread | Started in | What it does |
|--------|-----------|--------------|
| Main | `main.py:initialize_app` | The Flask dev server (`app.run`), handling HTTP |
| `AuthBotThread` (daemon) | `main.py:114` | Owns its own asyncio loop, runs the Discord bot |
| `job-scheduler` (daemon, SQLite only) | `core/jobs.py:start_inline_scheduler`, called from `main.py` | Runs periodic jobs, e.g. hourly refresh-token cleanup. On Postgres the worker process runs them instead. |

### Background jobs

Modules declare jobs in a `jobs.py` with `@job(name, cron=..., retry=...)` from `core/jobs.py`,
list that file in `JOB_MODULES` in `modules/registry.py`, and start one with
`jobs.defer(name, **kwargs)`.

| Job | Schedule | What it does |
|-----|----------|--------------|
| `auth.cleanup_tokens` | hourly | Deletes expired refresh tokens |
| `points.import_event_csv` | on CSV upload | Awards event points from an attendance CSV |
| `calendar.sync_all` | `CALENDAR_SYNC_CRON`, unset by default | Notion to Google sync for every enabled org |
| `audit.prune` | daily, 03:30 | Deletes audit rows older than `AUDIT_RETENTION_DAYS` |

Every run of a job declared with `audit=True` (the default) is written to `audit_log`.

How they run depends on the database:

- **Postgres:** Procrastinate. `defer` inserts a row in `procrastinate_jobs`; the `worker` compose
  service (`worker_main.py`, postgres profile) runs it, retries failures, and schedules periodic
  jobs. Job history is the `procrastinate_jobs` table. The schema comes from the Alembic migration
  `e4b8c1f0a7d3`; upgrading procrastinate needs a migration that applies its SQL migrations.
- **SQLite:** no queue. `defer` runs the job in a thread of the calling process and periodic jobs
  run from a thread in the API, which is what the platform did before. `worker_main.py` exits.

`JOBS_BACKEND=inline|procrastinate` overrides the choice; the tests use `inline`.

Because the bot lives in a separate thread with its own event loop, Flask request handlers cannot
`await` bot calls. Instead they call **synchronous** helper methods on the bot object
(`auth_bot.check_officer(...)`, `auth_bot.check_user_membership(...)`), which read from py-cord's
in-memory guild/member cache. This is why so many endpoints return `503 Bot not available` when the
bot has not finished connecting: the cache is not populated yet.

The bot instance the API actually uses is `current_app.auth_bot`, set from inside the bot thread.
Handlers reach it via `current_app.auth_bot if hasattr(current_app, "auth_bot") else None`.

> **Production note:** the app is served by `app.run()` — Flask's development server — not by
> gunicorn, even though gunicorn is a declared dependency. See [Gotchas](./10-gotchas-and-known-issues.md).

## How a request flows

Take `POST /api/points/soda/assign_points`:

```
Browser
  │  Authorization: Bearer <JWT>
  │  X-Organization-ID / X-Organization-Prefix (added by the axios interceptor)
  ▼
Flask CORS check (origin must be in the allowlist in shared.py)
  ▼
Blueprint routing: points_blueprint, registered at /api/points
  ▼
@auth_required decorator (modules/auth/decoraters.py)
  │  ├─ session cookie token? validate it
  │  └─ else Authorization header token? validate it
  │  On failure: 401 (invalid) or 403 (expired)
  ▼
Handler: assign_points_to_org(org_prefix="soda")
  ├─ db = next(db_connect.get_db())            ← a fresh SQLAlchemy session per request
  ├─ look up Organization by prefix, is_active
  ├─ look up User by email → uuid → username
  ├─ verify UserOrganizationMembership exists and is_active
  ├─ insert a Points row
  └─ finally: db.close()
  ▼
jsonify(...) → response
```

Two things are worth internalising:

1. **Org scoping is per-request and manual.** There is no middleware that resolves the org. Every
   handler that needs one starts by querying `Organization` by `prefix` from the URL. The
   `X-Organization-ID` / `X-Organization-Prefix` headers the frontend sends are, in practice,
   **ignored by the backend** — the URL segment is what counts.
2. **Session lifecycle is manual.** Handlers do `db = next(db_connect.get_db())` and must
   `db.close()` in a `finally`. There is no Flask teardown hook doing it for you. Forgetting the
   `finally` leaks a connection.

## The module pattern

Every feature is a folder under `modules/`:

```
modules/<name>/
├── README.md    What the module does, its files, routes, jobs, tools and tables
├── service.py   The logic. Takes a DB session and plain values. Does not import Flask
├── api.py       Flask blueprint. Reads the request, calls service.py, returns JSON
├── models.py    SQLAlchemy tables, each inheriting core/base.py:Base
├── jobs.py      Background jobs (@job from core/jobs.py)
└── tools.py     Tools for agents (@tool from core/tools.py), served over MCP and /api/tools
```

A module has only the files it needs. REST routes, the bot, jobs and tools all call the same
`service.py` functions, which raise a subclass of `core.errors.ServiceError(message, status)`.
Routes for machine tokens use `machine_route` from `modules/auth/routes.py`. The older SoDA modules
(`points`, `storefront`, `users`) still keep most logic in `api.py`.

Shared code that is not a feature lives in `core/` (database, config, jobs, tools, secrets, audit,
logging, Discord and RunPod clients). `core/` must not import from `modules/`; three existing
imports are listed as exceptions in `pyproject.toml` until they are moved.

`make ci` runs `lint-imports` (import-linter) to enforce both rules. [Writing a
module](./writing-a-module.md) lists every place a new module is registered.

Blueprints are mounted by `modules/registry.py` (`MOUNTS`), which `main.py` calls. `MOUNTS` is the
list of every URL prefix and the org switch that gates it.

Points, storefront, calendar, leetcode and compute are optional: an officer can turn them off for their org, and then
that org's routes in the module return 404 (the public leaderboard follows the points switch).
Switches live in `Organization.config["modules"]`; a missing entry means on, so existing orgs are
unchanged. The list is `OPTIONAL_MODULES` in `modules/organizations/service.py`.

Plus `GET /health`, defined directly in `main.py`, which returns the git commit hash and process
start time — that is how you confirm which build is live.

## The `shared.py` hub, and its circular-import tax

`shared.py` holds the process-wide singletons: `app`, `config`, `db_connect`, `tokenManager`,
`notion`, `logger`, `create_auth_bot`. Nearly every module does `from shared import ...`.

Because `shared.py` itself imports from `modules/`, you get import cycles. The codebase works
around them with **deferred imports inside functions**, which you will see constantly:

```python
def check_officer(self, user_id, superadmin_user_id):
    from modules.organizations.models import Organization   # imported here, not at module top
    from shared import db_connect
```

This is intentional, not sloppiness. If you move an import to the top of a file and get an
`ImportError` at startup, that is why — put it back.

## Multi-organization model

An **Organization** is a Discord guild registered in the database. Every domain object that belongs
to a club — points, products, orders, order items, calendar links — carries an `organization_id`
foreign key. Users are global (one row per human across all orgs) and are joined to orgs through
`UserOrganizationMembership`.

Authorization is delegated to Discord:

- **Officer** = has the guild's `officer_role_id` role. Checked live via `BotFork.check_officer`.
- **Member** = present in the guild at all. Checked via `BotFork.check_user_membership`.
- **Superadmin** = Discord ID equals `config.SUPERADMIN_USER_ID`.

None of these are stored as roles in the database. They are read from Discord's cache every time.
That means: change someone's Discord role, and their platform access changes on the next request.
It also means if the bot is offline, nobody can prove they are an officer.

## External services

| Service | Used for | Where |
|---------|----------|-------|
| Discord (gateway + REST) | Login, role/membership checks, the bot itself | `modules/bot/`, `modules/games/`, `modules/leetcode/`, `modules/auth/api.py` |
| Clerk | Auth for the public-facing member storefront | `core/clerk_auth.py` |
| Notion | Source of truth for club events | `modules/calendar/clients.py:NotionCalendarClient` |
| Google Calendar | Destination for synced events | `modules/calendar/clients.py:GoogleCalendarClient` |
| LeetCode GraphQL | Daily/random problems, verifying solves | `modules/leetcode/client.py` |
| Sentry | Errors, logs, and calendar-sync performance traces | `shared.py`, `modules/calendar/utils.py` |
| Google Sheets | One-off distinguished-member import | `modules/users/user_reader.py` (not wired to any route) |
