# 5. Backend Modules

One section per folder under `modules/`. For the exact HTTP surface see the
[API Reference](./06-api-reference.md); this page explains what each module is *for* and where the
interesting logic lives.

---

## `modules/utils` — the foundation

Everything else imports from here. Nothing here imports from other domain modules (except lazily,
inside functions, to break cycles).

| File | Contents |
|------|----------|
| `base.py` | Four lines: the single `Base = declarative_base()`. Every model inherits from this one object, which is what makes `create_all` and Alembic autogenerate work. |
| `db.py` | `DBConnect`: creates the engine and `SessionLocal`, ensures `./data/` exists, calls `create_all`. Also carries a set of storefront CRUD helpers (`create_storefront_product`, `get_storefront_orders`, `update_storefront_product_stock`, …) that the storefront API calls into. |
| `config.py` | `Config`: reads `.env` via python-dotenv into ~40 attributes. Also loads `google-secret.json` from the repo root into `GOOGLE_SERVICE_ACCOUNT` (warns and sets `None` if absent). |
| `logging_config.py` | `setup_logger()` builds a colorlog handler on the root logger at INFO. Use `get_logger(__name__)` in new code. **Never use `print()`** — the project instruction is explicit about this. |
| `TokenManager.py` | RSA keypair management and all JWT issue/verify/refresh/revoke logic. See [Authentication](./04-authentication.md). |
| `clerk_auth.py` | `verify_clerk_token()` and `@require_clerk_auth`. |
| `types.py` | `ExtendedRequest`, a Flask `Request` subclass declaring `clerk_user_email`. Type-checker sugar only — the real attribute is set dynamically on `flask.request`. |

`DBConnect.get_db()` is a generator, used everywhere as `db = next(db_connect.get_db())`. You must
close it yourself in a `finally`.

---

## `modules/auth` — login and the decorators

- **`api.py`** — the Discord OAuth endpoints (`/login`, `/callback`), token lifecycle
  (`/refresh`, `/revoke`, `/logout`), and validation helpers (`/validToken`, `/validateToken`,
  `/name`, `/appToken`).
- **`decoraters.py`** — `@auth_required`, `@dual_auth_required`, `@superadmin_required`,
  `@member_required`, `@error_handler`. This file is imported by every other module. Fully
  documented in [Authentication](./04-authentication.md).
- **`models.py`** — `Session` (unused) and `RefreshToken`.

There is a hardcoded `GUILD_ID = 762811961238618122` at the top of `api.py`; it is unused there, but
the same constant is hardcoded inside `BotFork.get_name()`, which means **display names are always
resolved from SoDA's own Discord server** regardless of which org the user belongs to.

---

## `modules/organizations` — multi-tenancy

- **`models.py`** — `Organization`, `OrganizationConfig`, `Officer`.
- **`config.py`** — `OrganizationSettings`, a dataclass of default per-org settings (Discord
  integration, points system, event management, member management, calendar) with `to_dict()` /
  `from_dict()`. Written into `Organization.config` when an org is created.
- **`api.py`** — read/update endpoints for an org, its stats, its recent activity, its settings, its
  calendar config, and its Discord roles. All `@auth_required`, all keyed by numeric `org_id`
  (unlike most of the codebase, which uses `org_prefix`).

`GET /api/organizations/` is what the frontend uses to build the org switcher.

---

## `modules/points` — members and the points ledger

The largest module (~1300 lines). Two halves: shared helper functions, then routes.

### Helper functions (top of `api.py`)

| Function | What it does |
|----------|--------------|
| `update_user_field(db, user, field, value, org_id)` | Sets one field with uniqueness validation on `username`/`email`/`discord_id`/`asu_id`. Returns `(success, message)`. |
| `manage_user_in_organization(db, org_id, user_data, discord_id, user_identifier)` | The central find-or-create-and-enrol routine. Everything else funnels through it. |
| `get_or_create_user(discord_id, org_id, username)` | Wrapper for Discord-originated users. |
| `link_or_create_user(org_id, user_data, discord_id)` | Wrapper for member-store logins. |
| `get_or_create_user_from_clerk(db, org_id, clerk_user, email)` | Wrapper for Clerk users. Derives a name from Clerk's first/last name, falling back to the email local part. Also called from the storefront checkout. |
| `process_csv_in_background(...)` | Parses an uploaded attendance CSV and awards points row by row, in a background thread. |

### Routes

Public/member: `member_login`, `member_profile`, `leaderboard`.
Officer (`@auth_required`): user CRUD, `add_points`, `assign_points` (aliased as `assignPoints`),
`get_points`, `getUserPoints`, `getUserTotalPoints`, `delete_points`, `uploadEventCSV`.

### The two things to remember

1. **Balance = `SUM(points)`.** There is no balance column. Spending inserts a negative row.
2. **Points require an active membership.** `assign_points` returns 400 if the user has no active
   `UserOrganizationMembership` in that org.

### CSV upload

`POST /<org_prefix>/uploadEventCSV` reads the file **into memory**, then spawns a plain
`threading.Thread` to process it and returns 202-style immediately. Consequences: no progress
reporting, no result reporting, errors only reach the log, and the work dies if the process
restarts mid-run. Fine for a few hundred rows; do not feed it a huge file.

---

## `modules/users` — member records within an org

Overlaps with `points` — both create and read users. `users` is the CRUD-shaped surface:
`viewUser`, `createUser`, `user` (GET/POST), `users` (list/create), `users/<identifier>`, and
`submit-form`. All org-scoped by prefix and `@auth_required`, except `submit-form`.

**`user_reader.py`** is separate and not wired to any route: a script that reads a hardcoded Google
Sheet of form responses (`SAMPLE_SPREADSHEET_ID`) and inserts anyone marked as a distinguished
member. It requires a `token.json` OAuth file generated by a `generate_token.py` script that is not
in this repository. Treat it as a historical one-off import tool.

---

## `modules/storefront` — merch paid in points

Three concentric surfaces, each with different auth:

| Surface | Routes | Auth |
|---------|--------|------|
| **Admin** | `products` CRUD, `orders` list/get/update-status/delete | `@auth_required` |
| **Clerk member** | `orders`, `orders/<email>`, `wallet/<email>`, `checkout` | `@dual_auth_required` |
| **Discord member** | `members/store`, `members/orders`, `members/orders/<id>`, `members/points` | `@member_required` |
| **Anonymous** | `products` (GET), `products/<id>` (GET), `store` (GET) | none |

### Checkout (`clerk_checkout`, `modules/storefront/api.py:964`)

The most important transaction in the codebase:

```
1. Resolve org by prefix
2. Find User by email == request.clerk_user_email
   └─ not found and we have a Clerk user? create via get_or_create_user_from_clerk
3. Require an active UserOrganizationMembership          → else 403
4. points_sum = SUM(Points.points) for (user, org)
5. points_sum < total_amount?                            → 400 "Insufficient points"
6. For each item: validate keys, load product, check stock, decrement stock in memory
7. Create Order (status="completed") + OrderItems via db_connect.create_storefront_order
8. Insert a Points row of -total_amount, event="Storefront Purchase - Order #<id>"
9. db.commit()
```

Note there is no explicit transaction boundary or row locking around the balance check and the
deduction. Two concurrent checkouts by the same user can both pass step 5. SQLite's single-writer
behaviour makes this unlikely in practice but it is not prevented by the code.

`normalize_category()` maps free-text categories onto the fixed list in
`web/src/constants/productCategories.js`.

---

## `modules/superadmin` — installing organizations

All routes are `@superadmin_required` (which, per the auth doc, really means "officer somewhere").

- `GET /check` — the only true superadmin identity check (`discord_id == SUPERADMIN_USER_ID`).
  Returns 403 with `{"is_superadmin": false}` for everyone else.
- `GET /dashboard` — lists guilds the bot is in that are **not yet** registered as organizations,
  plus the caller's officer orgs. This is the "add an org" picker.
- `GET /guild_roles/<guild_id>` — Discord roles in a guild, for choosing the officer role.
- `PUT /update_officer_role/<org_id>` — set `Organization.officer_role_id`.
- `POST /add_org/<guild_id>` — create an `Organization` from a guild: prefix derived from the guild
  name (lowercase, spaces/hyphens → underscores), default `OrganizationSettings` into `config`.
- `DELETE /remove_org/<org_id>` — hard `db.delete(org)`. There is **no cascade configured on
  Organization's children**, so this will fail or orphan rows if the org has points, products or
  orders. Treat as dangerous.

---

## `modules/public` — unauthenticated reads

Small, deliberately read-only: `favicon.ico`, `getnextevent`, per-org `leaderboard`, a global
`leaderboard`, per-org `users`, per-org `stats`. Wrapped in `@error_handler`. This is the surface
the public-facing website consumes.

---

## `modules/calendar` — Notion → Google Calendar

Four files plus models:

| File | Role |
|------|------|
| `clients.py` | `GoogleCalendarClient` (create/update/get/batch-delete events; create/get/list/delete calendars) and `NotionCalendarClient` (query a database, write a gcal id back to a page). |
| `service.py` | `MultiOrgCalendarService` — the orchestration. Also a thin legacy `CalendarService`. |
| `models.py` | `CalendarEventDTO` (a dataclass, `from_notion()` → `to_gcal_format()` / `to_frontend_format()`) and the `CalendarEventLink` table. |
| `utils.py` | `DateParser` (parse Notion dates, `ensure_end_date` defaults to +1 hour or a 1-day all-day span), `extract_property` (pull a typed value out of Notion's property JSON), `operation_span` (Sentry tracing), `batch_operation` (Google batch API helper). |
| `errors.py` | `APIErrorHandler` — normalises Google `HttpError`, Notion `APIResponseError`, and generic exceptions into Sentry-tagged logs. |

### Notion property names are hardcoded

`CalendarEventDTO.from_notion` expects exactly these properties: **`Name`** (title),
**`Date`** (date), **`Location`** (select), **`Description`** (rich_text), **`gcal_id`** (rich_text).
Rename a column in Notion and events silently stop syncing — `from_notion` returns `None` and logs a
warning.

### The sync algorithm (`sync_organization_notion_to_google`)

```
org must have notion_database_id           → else error
org.google_calendar_id missing?            → ensure_organization_calendar() creates one
                                              named "<Org Name> Events", in config.TIMEZONE
fetch all pages from the Notion database
parse each into a CalendarEventDTO (skipping malformed ones)
fetch all existing Google Calendar events
build a lookup by notionPageId (stored in Google's extendedProperties)
for each Notion event: create it, or update it if the content changed
delete duplicate Google events pointing at the same Notion page
delete orphaned Google events whose Notion page no longer exists
org.last_sync_at = now
```

`sync_all_organizations()` loops this over every org with `calendar_sync_enabled`.

### Sync is manual

**There is no background scheduler for calendar sync.** Older documentation claims it runs every
120 minutes; no such thread exists in the code. Sync happens only when something calls
`POST /api/calendar/<org_prefix>/sync` or `POST /api/calendar/sync-all`. If you want it periodic,
you need an external cron hitting those endpoints, or a new thread.

---

## `modules/bot` — Discord

Covered in full in [Discord Bot](./07-discord-bot.md). Structurally:

```
modules/bot/
├── api.py                          HTTP control surface for Jeopardy (/api/bot/*)
├── models.py                       jeopardy_game, active_game, leetcode_link, leetcode_solve
└── discord_modules/
    ├── bot.py                      BotFork (extends commands.Bot)
    ├── cogs/
    │   ├── HelperCog.py            Guild plumbing: channels, roles, messages, reactions
    │   ├── GameCog.py              Jeopardy orchestration inside Discord
    │   ├── LeetCodeCog.py          Daily challenge, verification, slash commands
    │   ├── UI.py                   discord.ui.View button components
    │   └── jeopardy/               Pure game model: Jeopardy, JeopardyQuestion, Team, QuestionPost
    └── utils/leetcode.py           LeetCode GraphQL client
```
