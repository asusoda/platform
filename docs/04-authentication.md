# 4. Authentication & Authorization

This is the most confusing part of the codebase, because there are **three separate auth systems**
running side by side. Read this page before touching anything auth-related.

## The three systems

| System | Who uses it | Credential | Verified by |
|--------|-------------|-----------|-------------|
| **Discord OAuth + local JWT** | Officers, in the admin web app | RS256 JWT issued by this API | `modules/utils/TokenManager.py` |
| **Clerk** | Members, on the public storefront | Clerk session token | `modules/utils/clerk_auth.py` (Clerk SDK) |
| **Flask session cookie** | Member store login, legacy paths | Signed cookie | Flask's built-in session |

They overlap. Some endpoints accept exactly one; some accept either; the storefront accepts all
three depending on the route.

---

## System 1: Discord OAuth → local JWT (the officer flow)

This is the main admin path. End to end:

```
1. Browser        → GET  {API}/api/auth/login
2. API            → 302 to discord.com/oauth2/authorize?...&scope=identify%20guilds
3. User approves on Discord
4. Discord        → 302 to REDIRECT_URI  ({API}/api/auth/callback?code=…)
5. API /callback  → POST discord.com/api/v10/oauth2/token   (exchange code for access token)
                  → GET  discord.com/api/v10/users/@me      (fetch the user's id)
                  → auth_bot.check_officer(user_id, SUPERADMIN_USER_ID)
                       ├─ superadmin? return every guild id
                       └─ else: for each active org with an officer_role_id,
                                look up the guild + role + member in the bot's cache,
                                collect guild ids where the member holds the role
6a. Officer in ≥1 org →
       tokenManager.generate_token_pair(username, discord_id,
                                        access_exp_minutes=30, refresh_exp_days=7)
       session["user"]  = {username, discord_id, role: "officer", officer_guilds: [...]}
       session["token"] / session["refresh_token"]
       302 → {CLIENT_URL}/auth/?access_token=…&refresh_token=…
6b. Not an officer →
       302 → {CLIENT_URL}/auth/?error=Unauthorized Access
7. React /auth page (TokenRetrival.js) reads the query params into localStorage
```

Two consequences worth flagging:

- **The bot must be connected and its guild cache warm**, or `/callback` returns
  `503 Authentication service temporarily unavailable`.
- **Tokens travel in the URL query string** in step 6a. They land in browser history and in any
  proxy access log along the way.

### The tokens themselves

`TokenManager` (`modules/utils/TokenManager.py`):

- Algorithm **RS256**, with an RSA keypair stored at `./data/jwt_private.pem` /
  `./data/jwt_public.pem`. Generated on first boot, `chmod 600` on the private key, and reloaded on
  subsequent boots so tokens stay valid across restarts.
- **Access token**: 30 minutes, payload carries `username` and `discord_id`.
- **Refresh token**: 7 days. The random token is returned to the client, but only its
  **SHA-256 hash** is stored in the `refresh_tokens` table. A stolen database does not yield usable
  refresh tokens.
- **Blacklist**: `TokenManager.blacklist` is an **in-memory set**. `delete_token()` adds to it.
  It is emptied on every restart and is not shared across processes.

Key methods: `generate_token_pair`, `refresh_access_token`, `revoke_refresh_token`,
`cleanup_expired_refresh_tokens`, `is_token_valid`, `is_token_expired`, `decode_token`,
`retrieve_username`, `retrieve_discord_id`, `generate_app_token`.

### The status-code convention (important)

The decorators distinguish these deliberately, and the frontend depends on it:

- **401** — token invalid, missing, or malformed → the client should log out.
- **403** — token valid but **expired (Authorization-header path)** → the client should refresh and retry.

Note: when the token comes from the Flask session (`session["token"]`), the current `@auth_required` implementation clears the session token and returns **401** on expiry, so 403-based refresh logic only applies to header-authenticated requests.
---

## System 2: Clerk (the member storefront)

`modules/utils/clerk_auth.py`.

`verify_clerk_token(token)`:

1. Wraps the bearer token in a synthetic `httpx.Request`.
2. Calls `clerk.authenticate_request(...)` with `authorized_parties` from
   `CLERK_AUTHORIZED_PARTIES` (comma-separated; falls back to `localhost:3000` and `localhost:5173`).
3. Pulls the user id (`request_state.user_id`, falling back to the JWT `sub` claim).
4. Calls `clerk.users.get(user_id)` and resolves the **primary email address** — falling back to the
   first listed address if there is no primary match.
5. Returns `(email, clerk_user)`, or `None` on any failure.

**The email is the identity.** The platform matches Clerk users to local `users` rows by
`User.email`. Change a member's email in Clerk and they become a different person to this system.

`@require_clerk_auth` sets `request.clerk_user_email` and `request.clerk_user` and calls through.

---

## System 3: Flask session cookies

Set in two places:

- `/api/auth/callback` stores `session["user"]`, `session["token"]`, `session["refresh_token"]`.
- `POST /api/points/<org_prefix>/member_login` stores `session["member_user_id"]` and
  `session["member_org_id"]`.

`@member_required` reads `session["discord_id"]` — which, note, **nothing in the current codebase
ever writes**. See [Gotchas](./10-gotchas-and-known-issues.md).

Sessions are signed with `app.secret_key`, which comes from `FLASK_SECRET_KEY` and **defaults to
`"dev-secret-key"`**. Set it in production.

---

## The decorators — `modules/auth/decoraters.py`

(The filename is misspelled. It is spelled that way everywhere; do not "fix" it casually, it is
imported by every module.)

### `@auth_required`

The workhorse. Used by most officer endpoints.

```
session["token"] present?
  ├─ invalid  → pop session, 401
  ├─ expired  → pop session, 401
  └─ ok       → proceed
else Authorization header?
  ├─ absent   → 401 "Authentication required!"
  ├─ invalid  → 401
  ├─ expired  → 403
  └─ ok       → proceed
```

Note it does **not** check org membership or officer status. It only proves "you hold a valid token
this API issued". Since tokens are only issued to officers at `/callback`, that is the de-facto
officer gate — but it is not re-checked per request, so an officer who loses their Discord role
keeps working access until their 30-minute token expires (and can refresh for up to 7 days).

### `@dual_auth_required`

Tries Clerk first, then falls back to the Discord JWT (session cookie, then header). On success it
always sets `request.clerk_user_email` — from the Clerk email, or from the JWT's `username` claim —
so downstream code has one field to read regardless of which system authenticated.

Used by the storefront endpoints that both officers and Clerk members hit: `get_orders`,
`create_order`, `get_user_orders_clerk`, `get_user_wallet_clerk`, `clerk_checkout`.

> Careful: in the JWT branch `clerk_user_email` is set to a Discord **username**, not an email. Any
> handler that treats that value as an email (as `clerk_checkout` does with
> `User.email == user_email`) will simply not find the user in the JWT case.

### `@superadmin_required`

Validates the token, then:

- **Session path**: requires `session["user"]["role"] == "admin"`. But `/callback` sets that role to
  `"officer"` — so this branch never passes. In practice everything goes through the header path.
- **Header path**: decodes the token, takes `discord_id`, calls `auth_bot.check_officer(discord_id,
  SUPERADMIN_USER_ID)`, and requires a non-empty result.

So `@superadmin_required` in effect means "**is an officer in at least one org**", not "is the
superadmin". The only endpoint that checks true superadmin identity is `GET /api/superadmin/check`,
which compares `discord_id` against `config.SUPERADMIN_USER_ID` inside the handler body.

Returns `503` when the bot is unavailable or not ready.

### `@member_required`

For public member-facing storefront routes. Requires `org_prefix` in the URL, reads
`session["discord_id"]`, loads the org, and calls
`auth_bot.check_user_membership(discord_id, guild_id)`. On success it injects `user_discord_id` and
`organization` into the handler's `kwargs` — which is why those handlers are declared with `**kwargs`.

### `@error_handler`

Catches any exception, logs it, and returns `{"error": str(e)}, 500`. Convenient, but it means a
handler wrapped in it will never surface a stack trace to the client and will convert programming
errors into 500s with the raw exception message in the body.

---

## Decorator ordering

Order matters — decorators apply bottom-up, so the one listed **first** runs **first**:

```python
@storefront_blueprint.route("/<string:org_prefix>/products", methods=["POST"])
@auth_required      # runs first: rejects unauthenticated callers
@error_handler      # runs second: wraps the handler body
def create_product(org_prefix): ...
```

Keep auth above `@error_handler`. Flipping them means auth failures get swallowed and re-reported
as 500s.

## Frontend side of the contract

- Tokens live in `localStorage` as `accessToken` and `refreshToken`.
- `web/src/components/utils/axios.js` attaches `Authorization: Bearer <token>` plus
  `X-Organization-ID` / `X-Organization-Prefix` from the `currentOrg` in `localStorage`.
- On a **403**, it POSTs to `/api/auth/refresh`, stores the new access token, and retries once
  (guarded by `_retry`). If refresh fails it clears `localStorage` and redirects to `/login`.
- `AuthContext.js` re-validates on mount and whenever the token changes; `useAuthToken` re-validates
  every 15 minutes.
