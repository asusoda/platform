# accounts

Lets an organization's agents connect a member's accounts at outside OAuth providers and read access tokens for them. Grants are stored encrypted, per organization and member.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Agent routes under `/members/<discord_id>`, the browser login flow and provider callbacks, member self-service under `/<org_prefix>/me` |
| `service.py` | Logins, encrypted grants, token refresh and pruning; declares the `accounts:link` and `accounts:token` scopes |
| `providers.py` | OAuth providers turned on by `ACCOUNTS_<NAME>_*` env vars, their token requests, and the Discord consent helpers |
| `models.py` | Grants and logins in progress |
| `jobs.py` | The prune job |

## Surface

- Routes: `/api/accounts`, no module switch. Agent routes take a machine token with `accounts:link` or `accounts:token`; `/<org_prefix>/me` routes take a member's Discord session; `/start`, `/discord/callback` and `/<provider>/callback` are browser redirects.
- Jobs: `accounts.prune`, cron `40 * * * *`.
- Tools: none.
- Tables: `account_grants`, `account_logins`.

## Depends on

`core.secrets`, `core.audit_http`, `core.errors`, `core.jobs`, `core.logging_config`, `core.base`; `modules.auth` (decorators, scopes), `modules.organizations.models`; `shared`.

## More

[docs/accounts.md](../../docs/accounts.md)
