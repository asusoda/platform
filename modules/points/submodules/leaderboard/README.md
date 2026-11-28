# points.leaderboard

A sub-module of `points`, switch `points.leaderboard`. Ranks the org's members by points, for officers, the public page and agents.

## Files

| File | Holds |
| --- | --- |
| `service.py` | `ranked_members()` and the leaderboards: the org's top members, the public page's, the officers' with each entry, and the one across every org |
| `tools.py` | The `points.leaderboard` tool |

## Surface

- Routes: none of its own. `GET /api/points/<org_prefix>/leaderboard` and `GET /api/public/<org_prefix>/leaderboard` need this switch and `points`. `GET /api/public/leaderboard` ranks every org and has no switch.
- Jobs: none.
- Tools: `points.leaderboard` (scope `points:read`). Names and totals only.
- Tables: none. It reads `points`, `users` and `user_organization_memberships`.
