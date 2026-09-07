# 2. Architecture

## The two containers

```
┌──────────────────────────────┐        ┌──────────────────────────────┐
│  soda-web       :5000        │        │  soda-internal-api  :8000    │
│  node:18-alpine              │──HTTP─▶│  python:3.12-slim            │
│  `serve -s build`            │        │  `python3 main.py`           │
│  Static React bundle         │        │  Flask + Discord bot thread  │
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
    ├─ starts a daemon thread: refresh-token cleanup, every 1 hour  │
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
| cleanup thread (daemon) | `shared.py:98` | Every 3600s, deletes expired rows from `refresh_tokens` |
| py-cord task loops | inside `AuthBotThread` | `post_daily` (every 24h at a fixed time) and `verify_loop` (every 10 min while a daily challenge is live) |

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

Every folder under `modules/` follows the same shape:

```
modules/<name>/
├── api.py       Blueprint + route handlers. This is the module's public surface.
├── models.py    SQLAlchemy models, all inheriting from modules/utils/base.py:Base
└── README.md    Older, module-local notes (treat as historical — see Gotchas)
```

Some modules add more: `calendar/` has `service.py`, `clients.py`, `utils.py`, `errors.py`;
`bot/` has the whole `discord_modules/` tree; `organizations/` has `config.py`.

Blueprints are registered in `main.py` with these prefixes:

| Blueprint | URL prefix |
|-----------|-----------|
| `public_blueprint` | `/api/public` |
| `points_blueprint` | `/api/points` |
| `users_blueprint` | `/api/users` |
| `auth_blueprint` | `/api/auth` |
| `calendar_blueprint` | `/api/calendar` |
| `game_blueprint` (from `modules/bot`) | `/api/bot` |
| `organizations_blueprint` | `/api/organizations` |
| `superadmin_blueprint` | `/api/superadmin` |
| `storefront_blueprint` | `/api/storefront` |

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
| Discord (gateway + REST) | Login, role/membership checks, the bot itself | `modules/bot/`, `modules/auth/api.py` |
| Clerk | Auth for the public-facing member storefront | `modules/utils/clerk_auth.py` |
| Notion | Source of truth for club events | `modules/calendar/clients.py:NotionCalendarClient` |
| Google Calendar | Destination for synced events | `modules/calendar/clients.py:GoogleCalendarClient` |
| LeetCode GraphQL | Daily/random problems, verifying solves | `modules/bot/discord_modules/utils/leetcode.py` |
| Sentry | Errors, logs, and calendar-sync performance traces | `shared.py`, `modules/calendar/utils.py` |
| Google Sheets | One-off distinguished-member import | `modules/users/user_reader.py` (not wired to any route) |
