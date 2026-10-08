# auth

Signs officers and members in with Discord and decides who may call what: platform tokens, app tokens, machine tokens for apps and agents, and the route decorators every other module uses.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Discord OAuth login and callback, one-time code exchange, refresh, revoke, logout, app tokens, `/machine/whoami` |
| `decoraters.py` | Route decorators: `auth_required`, `dual_auth_required`, `member_required`, `org_officer_required`, `superadmin_required`, `machine_scope_required`, `error_handler` |
| `access.py` | The caller behind a credential, officer and superadmin checks; refusals are logged only until `ACCESS_ENFORCE=true` |
| `tokens.py` | `TokenManager` and the `token_manager` instance: RS256 keys in `./data`, access and refresh tokens, app tokens, revocation |
| `clerk.py` | Clerk client and `verify_clerk_token` |
| `machine_tokens.py` | Issue, verify, revoke and list machine tokens; only a hash is stored |
| `scopes.py` | The registry of scopes that modules declare |
| `routes.py` | `officer_route` and `machine_route` route helpers, `json_body` and `token_org` |
| `models.py` | Sessions, refresh tokens, revoked tokens, app tokens, machine tokens |
| `jobs.py` | The refresh token cleanup job |

## Surface

- Routes: `/api/auth`, no module switch. Login, callback, exchange, refresh and logout are public; `/validToken`, `/revoke`, `/name` and the app token routes need a signed-in platform token; `/machine/whoami` takes a machine token.
- Jobs: `auth.cleanup_tokens`, cron `0 * * * *`.
- Tools: none.
- Tables: `sessions`, `refresh_tokens`, `revoked_tokens`, `app_tokens`, `machine_tokens`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
