# accounts

Lets an org's agents connect a member's accounts at outside OAuth providers (Canvas, Google, Microsoft) and read access tokens for them. Grants are encrypted, for each org and member. Agents can also read a member's own Canvas through the `canvas.*` tools.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Agent routes under `/members/<discord_id>`, the browser sign-in and provider callbacks, member routes under `/<org_prefix>/me` |
| `service.py` | Sign-ins, encrypted grants, token refresh and prune; declares the `accounts:link` and `accounts:token` scopes |
| `providers.py` | The providers that `ACCOUNTS_<NAME>_*` turn on, their token requests, and the Discord consent helpers |
| `canvas.py` | Canvas reads with one member's own grant: courses, assignments, grades, announcements, calendar, assignment grades |
| `tools.py` | The `canvas:read` scope and the `canvas.*` tools |
| `models.py` | Grants and sign-ins in progress |
| `jobs.py` | The prune job |

## Surface

- Routes: `/api/accounts`. Agent routes need a machine token with `accounts:link` or `accounts:token`. `/<org_prefix>/me` routes need a member's Discord session. `/start`, `/discord/callback` and `/<provider>/callback` are browser redirects.
- Jobs: `accounts.prune`, schedule `40 * * * *`.
- Tools: `canvas.courses`, `canvas.assignments`, `canvas.grades`, `canvas.announcements`, `canvas.calendar`, `canvas.assignment_grades`, scope `canvas:read`. They show only when the Canvas provider is on.
- Tables: `account_grants`, `account_logins`.

See [docs/modules/accounts.md](../../docs/modules/accounts.md).
