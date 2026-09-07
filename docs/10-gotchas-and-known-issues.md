# 10. Gotchas & Known Issues

Read this page before changing anything. Everything here was verified against the code on the
`docs/codebase-documentation` branch. Nothing here is speculation — each item names the file and
line where you can see it for yourself.

Items are grouped by how likely they are to bite you, not by severity.

---

## A. Documentation that disagrees with the code

The repo's own `CLAUDE.md` / `AGENTS.md` and the per-module `README.md` files predate several
refactors. Where they conflict with the code, the code wins.

| Claim | Reality |
|-------|---------|
| "Active modules: auth, bot, calendar, **merch**, organizations, …" | There is no `modules/merch`. It is `modules/storefront`. |
| "**Two** separate bot instances (summarizer and auth)" | One bot. There is no summarizer bot anywhere in the tree. |
| "Calendar Sync Service … runs every 120 minutes" | **No such scheduler exists.** Grep for `Thread(`, `time.sleep`, `tasks.loop`: the only background workers are the hourly refresh-token cleanup (`shared.py:98`), the LeetCode daily/verify loops, and the CSV thread. Calendar sync only happens when someone POSTs `/api/calendar/<org>/sync` or `/api/calendar/sync-all`. |
| `modules/README.md` lists endpoints like `/auth/login`, `/points/award`, models like `PointBalance`, `PointRule` | Those paths and models do not exist. Real paths are `/api/auth/login`, `/api/points/<org>/assign_points`; the only points model is `Points`. |
| `modules/storefront/README.md` schema | Missing `organization_id`, `category`, and `message` columns that the models actually have. |

**If you fix code documented here, fix `CLAUDE.md` too.** It is loaded into every AI agent session
and stale entries propagate.

---

## B. Things that are simply broken

### B1. `@member_required` can never succeed — all `/members/*` storefront routes are dead

`modules/auth/decoraters.py:335` reads `session.get("discord_id")` and returns
`401 Discord authentication required` when absent. **Nothing in the codebase ever writes
`session["discord_id"]`.** (`modules/points/api.py:419` also only reads it.)

Affected endpoints — every one of them returns 401 today:

- `GET  /api/storefront/<org>/members/store`
- `GET  /api/storefront/<org>/members/orders`
- `POST /api/storefront/<org>/members/orders`
- `GET  /api/storefront/<org>/members/orders/<id>`
- `GET  /api/storefront/<org>/members/points`

`web/src/pages/MemberStorePage.js` calls two of these, so the member store's order flow is
non-functional. The working member path is the Clerk one (`/checkout`, `/wallet/<email>`,
`/orders/<email>`).

Fix direction: either set `session["discord_id"]` during a Discord-linked member login, or migrate
those routes to `@dual_auth_required`.

### B2. Frontend Jeopardy/bot pages call routes that do not exist

The backend serves Jeopardy under `/api/bot/*`. These call something else:

| File | Calls | Should be |
|------|-------|-----------|
| `web/src/pages/ActiveGame.js` | `/games/active` | `/api/bot/getactivegame` |
| `web/src/pages/GamePanel.js` | `/games/list` | `/api/bot/getavailablegames` |
| `web/src/pages/Jeopardy.js` | `/jeopardy/games` | `/api/bot/getavailablegames` |
| `web/src/pages/BotControlPanel.js` | `/bot/status` | route is commented out in `modules/bot/api.py:30` |
| `web/src/components/AwardPanel.js:25` | `/api/awardpoints` | `/api/bot/awardpoints` |
| `web/src/components/SetupButton.js:17,28` | `/api/createchannels`, `/api/startactivegame` | `/api/bot/startactivegame`; no `createchannels` route exists |
| `web/src/components/GameBoard.js:11` | `/api/getgamequestions` | no such route |

Note also that `AwardPanel`, `SetupButton` and `GameBoard` use bare `axios` with **relative** URLs,
so they hit the web container's own origin, not the API at all.

### B3. `@superadmin_required` does not check superadmin

Two problems in `modules/auth/decoraters.py:140`:

1. The **session branch** requires `session["user"]["role"] == "admin"`, but
   `modules/auth/api.py` sets that role to `"officer"`. The branch is unreachable in practice.
2. The **header branch** only requires `auth_bot.check_officer(...)` to return a non-empty list —
   i.e. "is an officer in **any** org". Any officer of any registered organization can call
   `POST /api/superadmin/add_org/<guild_id>` and `DELETE /api/superadmin/remove_org/<org_id>`.

The only real superadmin check lives inside `GET /api/superadmin/check`'s handler body
(`modules/superadmin/api.py:56`), comparing `discord_id` to `config.SUPERADMIN_USER_ID`.

### B4. `Session` model would fail on insert

`modules/auth/models.py:17` uses `func.utcnow()`. There is no SQL function called `utcnow()` in
SQLite; the correct call is `func.now()`. Harmless only because nothing ever inserts into
`sessions`. If you start using that table, fix this first.

### B5. `auth_required` can raise IndexError

`modules/auth/decoraters.py:121`:

```python
token = request.headers["Authorization"].split(" ")[1]
```

This line sits **outside** the `try`. An `Authorization` header without a space (e.g. just
`Authorization: abc`) raises `IndexError` → HTTP 500 instead of a clean 401.
`@dual_auth_required` handles this correctly with `split(" ", 1)` and a length check — copy that
pattern.

---

## C. Security-relevant

### C1. `/api/bot/*` is entirely unauthenticated

Every route in `modules/bot/api.py` — ~16 endpoints including `startactivegame`, `endactivegame`,
`uploadgame`, `awardpoints`, `cleanactivegame` — has **no auth decorator at all**. Anyone who can
reach the API can create Discord channels and roles in the guild, start and end games, and award
points. Since the API is publicly reachable at `api.thesoda.io`, this is exposed.

### C2. Tokens travel in the URL query string

`modules/auth/api.py:94` redirects to
`{CLIENT_URL}/auth/?access_token=…&refresh_token=…`. Access and refresh tokens end up in browser
history, in the `Referer` header of any subsequent request, and in every proxy and CDN access log
on the path. A POST body or a `HttpOnly` cookie would avoid this.

### C3. `FLASK_SECRET_KEY` defaults to `"dev-secret-key"`

`main.py:23`. Sessions are signed with it. If it is not set in production, anyone can forge a
session cookie.

### C4. The token blacklist is in-memory and per-process

`TokenManager.blacklist` is a plain `set()` (`modules/utils/TokenManager.py:22`). `delete_token()`
adds to it. It is wiped on every restart, so "revoked" access tokens become valid again after a
deploy — until they expire naturally (30 min). Refresh-token revocation *is* persistent (DB-backed),
so the practical blast radius is one access-token lifetime.

### C5. `DELETE /api/superadmin/remove_org/<id>` has no cascade

`modules/superadmin/api.py:368` does a bare `db.delete(org)`. The `Organization` relationships are
declared with `backref` and **no `cascade`**, so its `points`, `products`, `orders`, `order_items`,
`memberships`, `officers` and `calendar_events` rows are not deleted. Depending on FK enforcement
you either get an integrity error or a pile of orphaned rows pointing at a nonexistent org. There is
no confirmation step and no soft-delete (`is_active=False`) alternative wired up in the UI.

### C6. Checkout has no transactional guard on the balance

`modules/storefront/api.py:964` reads `SUM(points)`, compares it to `total_amount`, then later
inserts the negative row and commits. Nothing locks the user's rows between the read and the write.
Two concurrent checkouts can both pass the balance check and overdraw the account. SQLite's
single-writer model makes this hard to hit but does not prevent it.

### C7. `@error_handler` leaks exception text

`modules/auth/decoraters.py:409` returns `{"error": str(e)}, 500`. Any exception message — including
SQLAlchemy errors that can contain query fragments — is returned to the client.

---

## D. Structural quirks you will trip over

### D1. `shared.py` builds a second, unused bot at import time

`shared.py:153`:

```python
bot = create_auth_bot(asyncio.get_event_loop())
```

This runs at import, builds a full `BotFork` with three cogs, and **is never started or used**. The
bot everything actually talks to is the one created inside `AuthBotThread` and attached as
`app.auth_bot` (`main.py:91`). If you import `bot` from `shared`, you get the dead one. Always use
`current_app.auth_bot`.

It also calls the deprecated `asyncio.get_event_loop()` outside a running loop, which emits a
`DeprecationWarning` on 3.12 and will be an error in a future Python.

### D2. Flask's dev server is the production server

`main.py:123` calls `app.run(...)`. `gunicorn==25.0.1` is a declared dependency but nothing invokes
it. `Dockerfile.api`'s `CMD` is `python3 main.py`. The dev server is single-threaded-by-default,
does not handle load, and is explicitly not intended for production use.

Why it was probably left this way: the Discord bot thread and the in-memory Jeopardy state assume a
**single process**. Running gunicorn with >1 worker would start one bot per worker and split the
game state. Any move to gunicorn has to solve that first.

### D3. `IS_PROD` vs `PROD` — two different variables

- `main.py:121` reads `os.environ["IS_PROD"]` to decide debug/reloader.
- `modules/utils/config.py:29` reads `PROD` into `config.PROD`, which nothing uses.

`.env.template` and `docker-compose.yml` set `IS_PROD`. `PROD` is dead.

### D4. `SYS_ADMIN` vs `ADMIN_USER_ID` — crossed wires

```python
self.SYS_ADMIN            = os.environ.get("ADMIN_USER_ID")   # config.py:74
self.SUPERADMIN_USER_ID   = os.environ.get("SYS_ADMIN")       # config.py:80
```

The attribute named `SYS_ADMIN` reads the env var `ADMIN_USER_ID`, and the attribute used for
superadmin checks reads the env var `SYS_ADMIN`. **Set `SYS_ADMIN` in `.env`.** `config.SYS_ADMIN`
is unused.

### D5. Database URL config is fiction

`config.py` defines `DB_TYPE`, `DB_URI`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
**None are read.** `shared.py:64` hardcodes `DBConnect("sqlite:///./data/user.db")`. `psycopg2-binary`
and `pymongo` are installed dependencies with no corresponding code. Setting `DB_URI` does nothing.

### D6. `create_all` runs three times, and coexists awkwardly with Alembic

`DBConnect.__init__` calls `check_and_create_tables()`, which calls `create_all` — and then, after a
stray docstring at `modules/utils/db.py:48`, contains a second block of **unreachable-in-effect**
logic that calls `create_all` again. `shared.py:74` calls it a third time.

The real consequence: a brand-new database gets its schema from the models, not from migrations, and
Alembic's version table stays empty. Then `alembic upgrade head` tries to create tables that already
exist. Fix by stamping: `uv run alembic stamp head` after a fresh `create_all` boot.

### D7. Circular imports are managed by function-level imports

`shared.py` imports from `modules/`, and `modules/` imports from `shared`. The workaround is
deferred imports *inside functions*, seen throughout (`bot.py:113`, `decoraters.py:33`,
`TokenManager.py:28`, `db.py:125`). Hoisting one of those to module scope will break startup with an
`ImportError`. This is deliberate.

### D8. `decoraters.py` is misspelled

It is spelled that way in every import across the codebase. Renaming it is a wide, mechanical change
— fine to do, but do it in its own commit.

### D9. CORS does not include `localhost:5000`

`shared.py:31` allows ports 3000 and 5173 on localhost, plus the two production hosts. But the dev
web container serves on **5000** (`package.json`: `PORT=5000 react-scripts start`, and
`Dockerfile.web`'s `serve -l 5000`). Browser calls from a locally-served frontend to a locally-served
API are blocked. Add your origin to the list when developing.

### D10. `X-Organization-ID` / `X-Organization-Prefix` headers are ignored

The axios interceptor sends them on every request (`web/src/components/utils/axios.js:21`). No
backend handler reads them. Org scoping comes entirely from the `<org_prefix>` URL segment. Do not
assume the headers are doing anything.

### D11. Two overlapping user APIs

`/api/points/<org>/users` and `/api/users/<org>/users` both create, read and update users, with
different response shapes. Check which one the page you are editing calls before changing either.

### D12. Jeopardy is single-instance and not org-aware

`GameCog.setup_game()` uses `self.bot.guilds[0]` — the first guild in the bot's cache, regardless of
which organization the request was for. `active_game` is queried with `.first()`. Live game state
(channels, roles, message references) lives on the cog instance in memory and is lost on restart,
leaving orphaned Discord channels and roles behind.

### D13. `BotFork.get_name()` is hardcoded to one guild

`modules/bot/discord_modules/bot.py:208` hardcodes guild `762811961238618122`. Used by
`/api/auth/callback` to get the display name. An officer of another organization who is not in
SoDA's own Discord server gets `None` as their username, which then becomes their JWT `username`
claim.

### D14. Notion property names are hardcoded

`CalendarEventDTO.from_notion` (`modules/calendar/models.py:45`) expects exactly `Name`, `Date`,
`Location`, `Description`, `gcal_id`. Rename a Notion column and events stop syncing silently —
`from_notion` returns `None` and logs a warning, and the event is simply skipped.

### D15. CSV upload is fire-and-forget

`modules/points/api.py:928` spawns a bare `threading.Thread`. No progress, no result reporting, no
persistence — errors reach the log only, and the work dies if the process restarts. Fine for a
few hundred rows.

### D16. `/api/calendar/<org>/events` hits Notion on every request

No caching. A page that polls it will rate-limit the club's Notion integration.

---

## E. Testing reality

`tests/test_api_endpoints.py` is the only test file. It is skipped entirely unless **both**
`BASE_URL` and `TEST_TOKEN` env vars are set:

```python
pytestmark = pytest.mark.skipif(
    not all(os.environ.get(v) for v in ("BASE_URL", "TEST_TOKEN")), ...
)
```

CI does not set them. So `make check`'s pytest step passes by skipping everything. There is **no
unit test coverage of any business logic** — not the checkout, not the points ledger, not the auth
decorators. Frontend coverage is the untouched CRA boilerplate test.

If you are adding logic to checkout, points, or auth, you are the first person to test it.

---

## F. Dead code and unused dependencies

| Item | Where |
|------|-------|
| `bot` singleton | `shared.py:153` |
| `Session` model, `sessions` table | `modules/auth/models.py:9` |
| `Officer` model, `OrganizationConfig` model | `modules/organizations/models.py` — superseded by live Discord checks and the `config` JSON column |
| `CalendarEventLink` table | created, but the sync path uses Google extendedProperties instead |
| `modules/users/user_reader.py` | Google Sheets importer; needs a `token.json` produced by a `generate_token.py` that is not in the repo |
| `Organization.points_per_message`, `points_cooldown` | no code reads them |
| `/botstatus`, `/startbot`, `/stopbot` | commented out, `modules/bot/api.py:27-49` |
| `web/src/components/GameTable.js` | zero-byte file |
| Commented-out `BotFork.setup_game` | `bot.py:261+` |
| Dependencies with no usage | `gunicorn`, `psycopg2-binary`, `pymongo`, `flask-socketio`, `python-socketio`, `flask-discord`, `selenium`, `webdriver-manager`, `gspread`, `oauth2client`, `anthropic`, `openai`, `google-genai`, `google-generativeai`, `dateparser`, `timefhuman` |
| Config values with no usage | `AVERY_BOT_TOKEN`, `AUTH_BOT_TOKEN`, `TNAY_API_URL`, `ONEUP_*`, `OPEN_ROUTER_CLAUDE_API_KEY`, `DISCORD_*_WEBHOOK_URL`, `GEMINI_API_KEY`, all `DB_*`, `PROD`, `SYS_ADMIN` (the attribute) |

That dependency list is worth a cleanup pass on its own — it inflates image size and the
vulnerability surface that Dependabot reports against.

---

## G. Quick pre-flight checklist

Before you open a PR:

- [ ] `make check` is green locally (it will push auto-fixes to your branch otherwise)
- [ ] Changed a model? Wrote a migration? `uv run alembic check` passes?
- [ ] New model module? Added it to the tuple in `alembic/env.py`?
- [ ] Touched a decorator or a status code? Confirmed 401-vs-403 still matches what the frontend
      interceptors expect ([Authentication](./04-authentication.md))?
- [ ] Added an endpoint? Does it have an auth decorator, and is it above `@error_handler`?
- [ ] Used `get_logger(__name__)` rather than `print()`?
- [ ] Opened a DB session with `next(db_connect.get_db())`? Closed it in a `finally`?
- [ ] Changed something this documentation describes? Updated the page — and `CLAUDE.md` if it
      contradicts you now?
