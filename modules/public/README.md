# public

Open routes for an organization's public pages: leaderboard, member list and stats, plus a leaderboard across all orgs.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Public leaderboard, users, stats, global leaderboard, favicon |
| `static/` | `favicon.ico` |

## Surface

- Routes: `/api/public`, no sign-in. `/<org_prefix>/leaderboard` is gated by the `points` switch; the rest are not gated. Member emails and ASU IDs are shown only to officers of the org and the superadmin.
- Jobs: none.
- Tools: none.
- Tables: none of its own; reads `users`, `user_organization_memberships`, `points`, `products` and `orders`.

## Depends on

`modules.auth` (access, decorators), `modules.points.models`, `modules.storefront.models`, `modules.organizations.models`; `shared`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
