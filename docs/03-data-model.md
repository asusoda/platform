# 3. Data Model

## Where the data lives

One SQLite file: `./data/user.db`. The URL is hardcoded in `shared.py`:

```python
db_connect = DBConnect("sqlite:///./data/user.db")
```

`DBConnect` (`core/db.py`) creates the engine with `check_same_thread=False` — required
because the bot thread and the Flask threads share the same engine — and builds a `sessionmaker`
called `SessionLocal`.

All models inherit from one declarative base, `core/base.py:Base`. That single `Base` is
what makes `Base.metadata.create_all()` and Alembic autogenerate see every table.

## Entity relationship overview

```
                          ┌──────────────────┐
                          │  organizations   │  ← one row per Discord guild
                          │  id, prefix,     │
                          │  guild_id,       │
                          │  officer_role_id │
                          └────────┬─────────┘
                                   │ organization_id on almost everything
        ┌──────────────┬───────────┼────────────┬─────────────┬──────────────┐
        ▼              ▼           ▼            ▼             ▼              ▼
 organization_    officers      points      products      orders    calendar_event_
    configs                        │            │            │           links
                                   │            │            │
                                   │            └──┬─────────┘
                                   │               ▼
                                   │          order_items
                                   │
   ┌────────┐   ┌───────────────────────────────┐
   │ users  │◀──│ user_organization_memberships │──▶ organizations
   └───┬────┘   └───────────────────────────────┘
       │
       ├──▶ points   (user_id)
       └──▶ orders   (user_id)

  Standalone (no org scoping):
   refresh_tokens · sessions · jeopardy_game · active_game · leetcode_link · leetcode_solve
```

## Tables, one by one

### `organizations` — `modules/organizations/models.py:Organization`

The tenant. One row per Discord server.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `name` | String(100) | Copied from the Discord guild name |
| `prefix` | String(20), unique | URL slug. Generated from the guild name on creation: lowercased, spaces and hyphens → underscores |
| `guild_id` | String(50), unique | Discord guild snowflake, stored as a string |
| `description`, `icon_url` | String | |
| `is_active` | Boolean, default `True` | Almost every query filters on this |
| `config` | JSON | An `OrganizationSettings` dict (see below) |
| `officer_role_id` | String(50), nullable | The Discord role that grants officer access. **If null, nobody can be an officer in this org** — `check_officer` skips orgs without it. |
| `points_per_message`, `points_cooldown` | Integer | Declared but not used by any current code path |
| `google_calendar_id` | String(255) | Filled in when a calendar is created for the org |
| `notion_database_id` | String(255) | Source Notion DB for this org's events |
| `calendar_sync_enabled` | Boolean, default `False` | |
| `last_sync_at` | DateTime | Updated after each successful sync |

Has a `to_dict()` used by the API responses.

### `organization_configs` — `OrganizationConfig`

A generic key/value store per org (`key` String, `value` JSON). Present in the schema; the
`Organization.config` JSON column is what the code actually uses today.

### `officers` — `Officer`

`(organization_id, user_id)` pairs. Also present but not authoritative — officer status is
determined live from Discord roles, not from this table.

### `users` — `modules/users/models.py:User`

One row per human, **global across all organizations**.

| Column | Notes |
|--------|-------|
| `id` | Integer PK |
| `discord_id` | unique, **nullable** — a member can exist without ever linking Discord |
| `username`, `email`, `student_id`, `uuid` | all unique, all nullable. `student_id` is the school's student number (was `asu_id`) |
| `name`, `class_standing`, `major` | profile fields. `class_standing` was `academic_standing` |
| `created_at` | |

Relationships: `points`, `orders`, `memberships`.

Because `email`, `username`, `student_id` and `discord_id` are each independently unique and nullable,
lookups throughout the codebase try several of them in sequence (email → uuid → username, or
discord_id → email). This is the single most common source of "user not found" bugs.

### `user_organization_memberships` — `UserOrganizationMembership`

The join table. `user_id` + `organization_id`, plus `joined_at` and `is_active`, with a unique
constraint `unique_user_org`. `profile_fields` (JSON object, JSONB on Postgres, default `{}`) holds
the fields an organization defines for its members, such as major or shirt size; each org sees only
its own. A user must have an **active** membership row before they can be
awarded points or check out in that org's store.

### `points` — `Points`

One row per point transaction. This is a **ledger, not a balance**.

| Column | Notes |
|--------|-------|
| `user_id`, `organization_id` | FKs |
| `points` | Float. **Negative values are how spending works** — a storefront purchase inserts a negative row. |
| `event` | Free-text label, e.g. `"General Meeting 3"` or `"Storefront Purchase - Order #12"` |
| `awarded_by_officer` | Free-text name, or `"System"` for automated deductions |
| `timestamp`, `last_updated` | |

A user's balance is always computed as `SUM(points)` filtered by user and org. There is no cached
balance column.

### `products` / `orders` / `order_items` — `modules/storefront/models.py`

- **`products`**: `name`, `description`, `price` (Float — priced in *points*, not dollars), `stock`,
  `image_url`, `category`, scoped by `organization_id`.
- **`orders`**: `user_id`, `organization_id`, `total_amount`, `status` (default `"pending"`),
  `message` (admin pickup instructions), plus a legacy `discord_user_id` string kept for backward
  compatibility.
- **`order_items`**: `order_id`, `product_id`, `quantity`, `price_at_time` (the price is snapshotted
  so later price changes do not rewrite history). `Order.items` cascades delete-orphan.

### `calendar_event_links` — `modules/calendar/models.py:CalendarEventLink`

Links a Notion page to a Google Calendar event for an org: `notion_page_id`,
`google_calendar_event_id`, `notion_database_id`, `google_calendar_id`, `event_metadata` JSON.

Note: the sync code in `modules/calendar/service.py` currently matches Notion pages to Google
events using Google Calendar's **extendedProperties**, not this table. The table exists and is
created but the live sync path does not depend on it.

### `refresh_tokens` — `modules/auth/models.py:RefreshToken`

`token` (a SHA-256 **hash** of the actual refresh token, not the token itself), `username`,
`discord_id`, `expires_at`, `created_at`. Persisted so refresh tokens survive an API restart. The
hourly `auth.cleanup_tokens` job deletes expired rows.

### `sessions` — `modules/auth/models.py:Session`

Declared, and the table is created, but **nothing reads or writes it**. Flask sessions are signed
cookies, not DB-backed. It also has a latent bug (`func.utcnow()` is not a real SQL function), which
is harmless only because the table is never inserted into.

### `jeopardy_game` / `active_game` — `modules/games/models.py`

- `jeopardy_game`: `name` + a `data` JSON blob — an uploaded game template.
- `active_game`: `name`, `game_data` JSON, `helper_data` JSON — the single currently-running game.
  The code treats this as a singleton (queries `.first()`), so only one game runs at a time across
  the whole deployment.

### `leetcode_link` / `leetcode_solve` — `modules/leetcode/models.py`

- `leetcode_link`: `discord_id` (PK) → `leetcode_username`. Written by the `/link` slash command.
- `leetcode_solve`: `discord_id`, `title_slug`, `solved_date`, with a unique constraint
  `uq_solve_user_date` — **one recorded solve per user per day**. That constraint is what makes the
  leaderboard a "daily streak" count rather than a raw problem count.

Neither is scoped to an organization. LeetCode features are global across all guilds the bot is in.

### `audit_log` — `core/audit.py:AuditEntry`

One row per successful API write (POST, PUT, PATCH, DELETE below 400, plus `GET /api/auth/appToken`,
which creates a token) and per job run. Columns: `created_at`, `source` (`api` or `job`), `action`
(method and route rule, or `job <name>`), `org` (prefix), `actor_kind` and `actor_id` (Discord id,
member email, or job name), `status`, `details` (request path, or job result and small arguments).
Request bodies and file contents are never stored. `/api/auth/refresh` is skipped. The daily
`audit.prune` job deletes rows older than `AUDIT_RETENTION_DAYS` (default 365).

### `org_secrets` — `core/secrets.py:OrgSecret`

Per-org integration tokens, one row per org and secret name, encrypted with Fernet using
`SECRETS_KEY`. Modules declare the names they read with `secrets.declare()`. Calendar reads
`notion_api_key` and `google_service_account` in place of the instance-wide `NOTION_API_KEY` and
`google-secret.json` when an org has saved them. The API lists which secrets are set but never returns a value.

## Migrations (Alembic)

Migrations live in `alembic/versions/`. Current chain:

```
d2ba7436c1b7  initial schema
      ↓
86f53887ffdc  add refresh_tokens table
      ↓
bba7ee211888  add sessions table + products.category   ← intentionally a NO-OP
      ↓
a1b2c3d4e5f6  add leetcode_link and leetcode_solve     ← head
```

`bba7ee211888` is deliberately empty: both objects it names were already created by the initial
schema, so re-creating them would fail on a fresh database. The docstring in the file says so.

### Running them

```bash
make migrate                                   # alembic upgrade head
uv run alembic revision --autogenerate -m "…"  # create a new migration
uv run alembic check                           # fail if models drift from migrations
uv run alembic downgrade -1                    # step back one
```

`make check` runs `alembic upgrade head` followed by `alembic check`, so **if you change a model and
do not write a migration, CI fails.** That is the guardrail.

### Two things to know about `alembic/env.py`

1. It **stubs out `shared`** before importing any model module. Importing `shared` for real would
   boot the config, the database, the Discord bot and the background threads — none of which
   Alembic needs. If you add a new model module, add it to the `for model_module in (...)` tuple in
   `env.py`, or autogenerate will not see your table.
2. It uses `render_as_batch=True`, which is required for SQLite: SQLite cannot `ALTER COLUMN`, so
   Alembic emulates it by creating a new table, copying rows, and swapping. Keep this in mind — some
   operations that are trivial on Postgres are expensive or impossible here.
3. `DATABASE_URL` overrides the URL from `alembic.ini` when set.

### No `create_all` at startup

Nothing calls `Base.metadata.create_all()` when the app starts. Alembic owns the schema on SQLite
and Postgres alike; the API container runs `alembic upgrade head` before gunicorn. Tests build a
fresh schema with `create_all` in `tests/conftest.py`, and CI runs `alembic check` so the models and
migrations cannot drift.
