# points

Tracks the points an org's members earn. Officers add members, award points by hand or from an event attendance CSV, and read the leaderboard; members sign in with Clerk to see their profile.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member and points routes, CSV upload, leaderboard, member login and profile |
| `service.py` | The leaderboard builder for the officer, public and tool leaderboards; point totals and point JSON; declares the `points:read` scope |
| `csv_import.py` | The attendance CSV import that the `points.import_event_csv` job runs |
| `models.py` | Point entries |
| `tools.py` | The `points.leaderboard` tool |
| `jobs.py` | The CSV import job |

## Surface

- Routes: `/api/points`, gated by the `points` switch. Most routes need an officer of the org; `/<org_prefix>/leaderboard` is open and shows emails only to a signed-in caller; `/member_login` takes a Clerk token and `/member_profile` reads the session it sets.
- Jobs: `points.import_event_csv`, deferred by the CSV upload, no schedule.
- Tools: `points.leaderboard` (scope `points:read`, gated by `points`).
- Tables: `points`. Members and memberships are in `modules/users`.

## More

[docs/05-backend-modules.md](../../docs/05-backend-modules.md)
