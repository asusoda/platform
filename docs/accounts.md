# Accounts module

Members connect their own accounts (Canvas, Google Calendar, Outlook) once, and agents use them on
their behalf. The platform holds the OAuth grants, encrypted with `SECRETS_KEY`, and refreshes
access tokens. Agents keep no tokens of their own.

## Login

1. The agent calls `POST /api/accounts/members/<discord_id>/<provider>/login` and sends the member
   the returned `url`, privately. The link works once, for 10 minutes.
2. The link signs the browser in to Discord. The login continues only when that Discord account
   is the member the link was made for, so a forwarded link cannot connect someone else's account.
3. The browser goes on to the provider's consent page, then back to
   `/api/accounts/<provider>/callback` in the same browser session. The platform exchanges the code
   and stores the grant.

## Routes

Agent routes are under `/api/accounts/members/<discord_id>` and take a machine token. The org is
the token's.

| Method and path | Scope | Does |
|---|---|---|
| `GET /` | `accounts:link` | Connected providers, scopes and expiry. No tokens |
| `POST /<provider>/login` | `accounts:link` | Start a login. Returns `url`, `expires_at` |
| `DELETE /<provider>` | `accounts:link` | Remove the grant |
| `GET /<provider>/token` | `accounts:token` | `access_token`, `scopes`, `expires_at`. Refreshed when it expires within a minute. Written to the audit log |

`token` answers 404 when the member has not connected, 409 when they have to connect again (no
refresh token, or the provider revoked it, in which case the grant is deleted), 502 when the
provider is down, and 503 when `SECRETS_KEY` is missing or cannot decrypt the grant.

Other routes:

- `GET /api/accounts/providers`: providers enabled on this platform.
- `GET /api/accounts/<org>/me` and `DELETE /api/accounts/<org>/me/<provider>`: a member signed in
  with Discord lists and removes their own connections.

## Configuration

| Variable | Does |
|---|---|
| `ACCOUNTS_BASE_URL` | Public URL of this API. Required; providers redirect back to it |
| `ACCOUNTS_<NAME>_CLIENT_ID`, `ACCOUNTS_<NAME>_CLIENT_SECRET` | Turn a provider on. Names: `GOOGLE`, `CANVAS`, `MICROSOFT` |
| `ACCOUNTS_<NAME>_SCOPES` | Space separated. Defaults: Google calendar events read, Canvas everything the key allows, Microsoft calendar and mail read |
| `ACCOUNTS_<NAME>_AUTHORIZE_URL`, `ACCOUNTS_<NAME>_TOKEN_URL` | Override the endpoints. Canvas defaults to canvas.asu.edu, Microsoft to the common tenant |

Redirect URLs to register:

- In the Discord application (the one `CLIENT_ID` names): `<ACCOUNTS_BASE_URL>/api/accounts/discord/callback`.
- In each provider's app: `<ACCOUNTS_BASE_URL>/api/accounts/<provider>/callback`.

Provider apps are per platform for now. An org at another school with its own Canvas would need
per-org client settings, which can come from org secrets later.

`accounts.prune` runs hourly and deletes logins past their expiry.
