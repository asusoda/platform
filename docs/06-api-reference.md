# 6. API Reference

Base URL: `http://localhost:8000` in dev, `https://api.thesoda.io` in production.

**Auth column key**

| Symbol | Meaning |
|--------|---------|
| — | No authentication |
| `JWT` | `@auth_required` — valid Discord-OAuth-issued JWT (session cookie or `Authorization: Bearer`) |
| `DUAL` | `@dual_auth_required` — Clerk token **or** JWT |
| `MEMBER` | `@member_required` — Flask session `discord_id` + guild membership |
| `SESSION` | Member-login Flask session (`member_user_id` + `member_org_id`) |
| `SUPER` | `@superadmin_required` — valid JWT **and** officer in ≥1 org |

Anything marked `JWT` returns **401** for an invalid/missing token.

For requests authenticated via the `Authorization: Bearer <access_token>` header, an expired token returns **403** so the frontend can refresh and retry. For the Flask-session token path (`session["token"]`), the current decorators clear the session token and return **401** on expiry.

---

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | `{status, service, commit, started_at}`. `commit` is the git SHA baked in at build time (`GIT_COMMIT_HASH`), falling back to `git rev-parse HEAD`. Used by the container healthcheck and by CD verification. |

---

## `/api/auth` — `modules/auth/api.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/login` | — | 302 to Discord's OAuth consent screen (`scope=identify guilds`) |
| GET | `/callback` | — | OAuth callback. Exchanges the code, checks officer status via the bot, issues an access + refresh token pair, and redirects to `{CLIENT_URL}/auth/?access_token=…&refresh_token=…`. Non-officers get `?error=Unauthorized Access`. 503 if the bot is not ready. |
|| GET | `/validToken` | JWT | `{status, valid}` — note: expired tokens are rejected by `@auth_required` before this handler runs |
|| GET | `/validateToken` | — | `{status, valid, expired}` — does its own header parsing and returns `valid:true, expired:true` for a valid-but-expired token |
| POST | `/revoke` | JWT | Body `{refresh_token}`. Revokes the refresh token and blacklists the current access token. |
| POST | `/logout` | — | Body `{refresh_token}` (optional). Revokes, blacklists the header token, clears the Flask session. |
| GET | `/name` | JWT | `{name}` — the display name stored in the token |
| GET | `/appToken?appname=<name>` | JWT | Issues a long-lived app token for a named integration |
| GET | `/success` | — | A static confirmation string |

---

## `/api/organizations` — `modules/organizations/api.py`

All keyed by **numeric org id**, not prefix.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | JWT | All organizations the caller can see. Drives the frontend org switcher. |
| GET | `/<int:org_id>` | JWT | One organization |
| GET | `/<int:org_id>/stats` | JWT | Aggregate counts for the dashboard |
| GET | `/<int:org_id>/activity` | JWT | Recent activity feed |
| PUT | `/<int:org_id>/settings` | JWT | Update the `config` JSON |
| GET | `/<int:org_id>/calendar` | JWT | Read calendar settings (`google_calendar_id`, `notion_database_id`, `calendar_sync_enabled`, `last_sync_at`) |
| PUT | `/<int:org_id>/calendar` | JWT | Update those settings |
| GET | `/<int:org_id>/roles` | JWT | Discord roles in the org's guild (via the bot) |

---

## `/api/superadmin` — `modules/superadmin/api.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/check` | SUPER | `{is_superadmin: bool}`. 200 + true only when `discord_id == SUPERADMIN_USER_ID`; otherwise 403 + false. |
| GET | `/dashboard` | SUPER | Guilds the bot is in that are not yet registered, plus the caller's officer orgs |
| GET | `/guild_roles/<guild_id>` | SUPER | Roles in a guild, for picking the officer role |
| PUT | `/update_officer_role/<int:org_id>` | SUPER | Set `officer_role_id` |
| POST | `/add_org/<guild_id>` | SUPER | Register a guild as an organization |
| DELETE | `/remove_org/<int:org_id>` | SUPER | Hard-delete an organization. **No cascade — see Gotchas.** |

---

## `/api/points` — `modules/points/api.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | `{message: "Points"}` liveness stub |
| POST | `/<org_prefix>/member_login` | — | Body: `{name, username, email, asu_id, academic_standing, major}`. Links or creates a user, stores `member_user_id`/`member_org_id` in the session. |
| GET | `/<org_prefix>/member_profile` | SESSION | Profile + memberships + points for the session's member |
| GET | `/<org_prefix>/leaderboard` | — | Public points leaderboard for the org |
| POST | `/<org_prefix>/users` | JWT | Create or link a user into the org |
| GET | `/<org_prefix>/users` | JWT | All users in the org, with point totals |
| PUT/PATCH | `/<org_prefix>/users/<user_identifier>` | JWT | Update user fields (unique fields validated) |
| GET | `/<org_prefix>/users/<user_identifier>/points` | JWT | That user's point history |
| POST | `/<org_prefix>/add_points` | JWT | Award points |
| POST | `/<org_prefix>/assign_points` | JWT | Award points. Body: `{user_identifier, points, event, awarded_by_officer}`. `user_identifier` is matched against email → uuid → username. Requires an active membership. |
| POST | `/<org_prefix>/assignPoints` | JWT | Alias of the above (same handler, camelCase route kept for compatibility) |
| GET | `/<org_prefix>/get_points` | JWT | Point records for the org |
| GET | `/<org_prefix>/getUserPoints?discord_id=…` | JWT | One user's point history |
| GET | `/<org_prefix>/getUserTotalPoints?discord_id=…` | JWT | `{user_id, discord_id, username, organization_id, total_points}` |
| DELETE | `/<org_prefix>/delete_points` | JWT | Delete all point rows for a named event |
| POST | `/<org_prefix>/uploadEventCSV` | JWT | Multipart CSV upload. Returns immediately; processing happens on a background thread. Results and errors go to the log only. |

---

## `/api/users` — `modules/users/api.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Liveness stub |
| GET | `/<org_prefix>/viewUser` | JWT | Look up one user in the org |
| POST | `/<org_prefix>/createUser` | JWT | Create a user in the org |
| GET/POST | `/<org_prefix>/user` | JWT | Read or upsert a single user |
| GET | `/<org_prefix>/users` | JWT | List users in the org |
| POST | `/<org_prefix>/users` | JWT | Add a user to the org |
| GET | `/<org_prefix>/users/<user_identifier>` | JWT | One user by email / uuid / username |
| POST | `/<org_prefix>/submit-form` | — | Public form intake |

This module overlaps heavily with `/api/points/<org>/users`. Both exist; check which one the
frontend page you are touching actually calls before changing either.

---

## `/api/storefront` — `modules/storefront/api.py`

### Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/<org_prefix>/products` | JWT | Create a product |
| PUT | `/<org_prefix>/products/<int:product_id>` | JWT | Update a product |
| DELETE | `/<org_prefix>/products/<int:product_id>` | JWT | Delete a product |
| GET | `/<org_prefix>/orders/<int:order_id>` | JWT | One order with its items |
| PUT | `/<org_prefix>/orders/<int:order_id>` | JWT | Update order status / admin message |
| DELETE | `/<org_prefix>/orders/<int:order_id>` | JWT | Delete an order |
| POST | `/<org_prefix>/store/purchase` | JWT | Legacy purchase path |

### Public reads

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/<org_prefix>/products` | — | All products |
| GET | `/<org_prefix>/products/<int:product_id>` | — | One product |
| GET | `/<org_prefix>/store` | — | Storefront view (in-stock products) |

### Clerk-authenticated member flow

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/<org_prefix>/orders` | DUAL | Orders — scoped to the caller |
| POST | `/<org_prefix>/orders` | DUAL | Create an order |
| GET | `/<org_prefix>/orders/<user_email>` | DUAL | Orders for a specific email |
| GET | `/<org_prefix>/wallet/<user_email>` | DUAL | Point balance for a specific email |
| POST | `/<org_prefix>/checkout` | DUAL | **The real checkout.** Body: `{total_amount, items:[{product_id, quantity, price}]}`. Verifies membership, verifies `SUM(points) >= total_amount`, decrements stock, creates the order, inserts a negative `Points` row. 201 on success. |

### Discord-member flow

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/<org_prefix>/members/store` | MEMBER | Products visible to a guild member |
| GET | `/<org_prefix>/members/orders` | MEMBER | The member's orders |
| POST | `/<org_prefix>/members/orders` | MEMBER | Place an order |
| GET | `/<org_prefix>/members/orders/<int:order_id>` | MEMBER | One order |
| GET | `/<org_prefix>/members/points` | MEMBER | The member's balance |

---

## `/api/calendar` — `modules/calendar/api.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/debug/organizations` | — | Diagnostic list of orgs and their calendar config |
| GET | `/<org_prefix>/events` | — | Live-fetches from Notion and returns events in frontend format. Does **not** touch Google Calendar. |
| POST | `/<org_prefix>/sync` | JWT | Run a full Notion → Google Calendar sync for one org |
| POST | `/<org_prefix>/setup` | JWT | Create/attach a Google Calendar for the org |
| POST | `/sync-all` | JWT | Sync every org with `calendar_sync_enabled` |
| POST | `/notion-webhook` | JWT (inherited) | Deprecated. Delegates to `sync_all_organizations()`, so its auth decorator applies. |
| GET | `/events` | — | Deprecated stub. Always 400 with "use `/api/calendar/{org_prefix}/events`". |
| POST | `/delete-all-events` | — | Deprecated stub. Always 400. Does not delete anything. |

Note that `/<org_prefix>/events` reads from Notion on **every request** — no caching. A page that
polls this endpoint will hammer the Notion API.

---

## `/api/bot` — `modules/bot/api.py` (Jeopardy control)

> **No endpoint in this blueprint has an auth decorator.** Anyone who can reach the API can start,
> stop, upload, and score games. Treat this as a known security gap, listed in
> [Gotchas](./10-gotchas-and-known-issues.md).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | — | Index stub |
| GET | `/getavailablegames` | — | Uploaded game templates from `jeopardy_game` |
| GET | `/getgame` | — | One game template |
| POST | `/uploadgame` | — | Upload a game JSON. Validated by `is_valid_game_json`. |
| GET | `/gamedata` | — | Game data for the panel |
| POST | `/startgame` / `/stopgame` | — | Start / stop |
| POST | `/setactivegame` | — | Promote a template to the single `active_game` row |
| GET | `/getactivegame` | — | The active game |
| GET | `/getactivegamestate` | — | Board state |
| POST | `/cleanactivegame` | — | Clear the active game |
| POST | `/startactivegame` | — | Create Discord channels/roles and begin |
| POST | `/endactivegame` | — | End and announce winners |
| POST | `/revealquestion` | — | Post a question to Discord |
| POST | `/revealanswer` | — | Reveal the answer |
| POST | `/awardpoints` | — | Award points to a team |

Endpoints named `/botstatus`, `/startbot`, `/stopbot` exist only as commented-out code.

---

## `/api/public` — `modules/public/api.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/favicon.ico` | — | Served from `modules/public/static/` |
| GET | `/getnextevent` | — | The next upcoming event |
| GET | `/<org_prefix>/leaderboard` | — | Public leaderboard for one org |
| GET | `/leaderboard` | — | Global leaderboard across all orgs |
| GET | `/<org_prefix>/users` | — | Public user list for one org |
| GET | `/<org_prefix>/stats` | — | Public stats for one org |

---

## CORS

Configured once in `shared.py`. Allowed origins are a fixed list:

```
http://localhost:3000   http://127.0.0.1:3000
http://localhost:5173   http://127.0.0.1:5173
https://thesoda.io      https://admin.thesoda.io
```

Methods: `GET, POST, PUT, DELETE, OPTIONS`.
Allowed headers: `Content-Type, Authorization, X-Organization-ID, X-Organization-Prefix`.
`supports_credentials: True`.

Note the dev web container serves on **port 5000**, which is *not* in the allowlist. Browser calls
from `http://localhost:5000` to the API will be blocked by CORS. If you are running the web app
locally against the local API, add your origin to this list.
