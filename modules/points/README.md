# points

Keeps the points that an org's members earn. Officers add members, give points by hand or from an event attendance CSV, and read the leaderboard. Members sign in with Clerk to see their profile. Its sub-modules, each with its own switch, are `points.leaderboard` (`submodules/leaderboard/`), `points.checkins` (`submodules/checkins/`) and `points.store` (`submodules/store/`).

## Files

| File | Holds |
| --- | --- |
| `api.py` | `points_blueprint`; officer routes (`officer_route`): members, point entries, awards, the CSV upload and its runs |
| `member_api.py` | Member and public routes on the same blueprint: store sign-in, member profile, leaderboard |
| `service.py` | Point totals, the member list with points, a member's orgs, the member save and profile, the award, list and delete of entries, and the bodies of the routes; declares `points:read` and `points:write` |
| `models.py`, `tools.py` | Point entries and import runs; the `points.*` tools |

## Surface

- Routes: `/api/points`, behind the `points` switch. `/<org_prefix>/leaderboard` also needs `points.leaderboard`, and `/<org_prefix>/uploadEventCSV` needs `points.checkins`. Most routes need an officer of the org. `DELETE /<org_prefix>/entries/<id>` deletes one entry by its id; `DELETE /<org_prefix>/delete_points` deletes a member's first entry for an event. `/<org_prefix>/leaderboard` is open and shows emails only to a signed-in caller. `/member_login` needs a Clerk token, and `/member_profile` reads the session it sets.
- Imports: `GET /<org_prefix>/imports` lists the newest 20 runs and `GET /<org_prefix>/imports/<id>` returns one, with `rows_done` of `rows_total`, `awarded`, `skipped` (duplicate emails) and `errors` (`row`, `email`, `message`, at most 200). A bad `event_points` gets 400. Each org keeps its newest 50 runs.
- Jobs: none. The CSV import job is in `points.checkins`.
- Tools: `points.entries`, `points.history`, `points.imports` (scope `members:read`); `points.award`, `points.delete` (confirm) (scope `points:write`). `points.leaderboard` and `points.import_csv` are in the sub-modules. A member is an email, uuid, username or Discord id. `points.award` gives points to up to 100 members in one commit.
- Tables: `points`, `points_imports`. Members and memberships are in `modules/members`.
- Cache: `/<org_prefix>/users` and `/<org_prefix>/get_points` are kept for 30 seconds and the leaderboard for 300 seconds, with an ETag (`core/http/cached.py`). An API write, an MCP tool write and each batch of a CSV import drop them in every API process (`core.cache.publish`, over Postgres `NOTIFY`). On SQLite, a write from another process shows after the time runs out.

## Known gaps

- `POST /<org_prefix>/add_points` answers 400 for an unknown org, not 404, so it does not use `officer_route`.
