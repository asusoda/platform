# public

Open routes for an org's public pages: leaderboard, member list and stats, and a leaderboard for all orgs.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Public leaderboard, users, stats, the leaderboard for all orgs, and the favicon |
| `static/` | `favicon.ico` |

## Surface

- Routes: `/api/public`, with no sign-in. The `points` switch turns off `/<org_prefix>/leaderboard`. Member emails and student ids show only to officers of the org and the superadmin.
- Jobs: none.
- Tools: none.
- Tables: none of its own. It reads `users`, `user_organization_memberships`, `points`, `products` and `orders`.

## Known gaps

- No `service.py`. The views in `api.py` query the tables of points, users and storefront.
- `/getnextevent` returns no response, so the AIS deployment turns it off with `DISABLED_ROUTES`.
