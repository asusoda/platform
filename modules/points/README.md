# points

Keeps the points that an org's members earn. Officers add members, give points by hand or from an event attendance CSV, and read the leaderboard. Members sign in with Clerk to see their profile.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Member and points routes, CSV upload, leaderboard, member sign-in and profile |
| `service.py` | The leaderboard for the officer, public and tool routes; point totals; declares `points:read` |
| `csv_import.py` | The attendance CSV import that the `points.import_event_csv` job runs |
| `models.py`, `tools.py`, `jobs.py` | Point entries; the `points.leaderboard` tool; the CSV import job |

## Surface

- Routes: `/api/points`, behind the `points` switch. Most routes need an officer of the org. `/<org_prefix>/leaderboard` is open and shows emails only to a signed-in caller. `/member_login` needs a Clerk token, and `/member_profile` reads the session it sets.
- Jobs: `points.import_event_csv`, started by the CSV upload.
- Tools: `points.leaderboard` (scope `points:read`).
- Tables: `points`. Members and memberships are in `modules/users`.

## Known gaps

- Views in `api.py` open their own session, query and commit. Only the leaderboard is in `service.py`. Move the rest one route at a time, with the contract tests.
- The camelCase routes (`getUserPoints`, `getUserTotalPoints`) are aliases. See Cleanup in `docs/roadmap.md`.
