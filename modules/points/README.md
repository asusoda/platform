# points

Keeps the points that an org's members earn. Officers add members, give points by hand or from an event attendance CSV, and read the leaderboard. Members sign in with Clerk to see their profile.

## Files

| File | Holds |
| --- | --- |
| `api.py` | `points_blueprint`; officer routes: members, point entries, awards, the CSV upload and its runs |
| `member_api.py` | Member and public routes on the same blueprint: store sign-in, member profile, leaderboard |
| `service.py` | The leaderboards, point totals, the member list with points, a member's orgs, and the award, list and delete of entries; declares `points:read` and `points:write` |
| `csv_import.py` | The attendance CSV import: the run row, the parse, the award in batches of 25 rows, and `changed()`, which drops the org's cached reads in every process |
| `models.py`, `tools.py`, `jobs.py` | Point entries and import runs; the `points.*` tools; the CSV import job |

## Surface

- Routes: `/api/points`, behind the `points` switch. Most routes need an officer of the org. `DELETE /<org_prefix>/entries/<id>` deletes one entry by its id; `DELETE /<org_prefix>/delete_points` deletes a member's first entry for an event. `/<org_prefix>/leaderboard` is open and shows emails only to a signed-in caller. `/member_login` needs a Clerk token, and `/member_profile` reads the session it sets.
- Imports: `POST /<org_prefix>/uploadEventCSV` returns 202 with `import_id`. `GET /<org_prefix>/imports` lists the newest 20 runs and `GET /<org_prefix>/imports/<id>` returns one, with `rows_done` of `rows_total`, `awarded`, `skipped` (duplicate emails) and `errors` (`row`, `email`, `message`, at most 200). A bad `event_points` gets 400. Each org keeps its newest 50 runs.
- Jobs: `points.import_event_csv`, started by the CSV upload, once for each `import_id`. A job with no `import_id` (queued by an older API) runs with no run row.
- Tools: `points.leaderboard` (scope `points:read`); `points.entries`, `points.history`, `points.imports` (scope `members:read`); `points.award`, `points.import_csv`, `points.delete` (confirm) (scope `points:write`). A member is an email, uuid, username or Discord id. `points.award` gives points to up to 100 members in one commit.
- Tables: `points`, `points_imports`. Members and memberships are in `modules/members`.
- Cache: `/<org_prefix>/users` and `/<org_prefix>/get_points` are kept for 30 seconds and the leaderboard for 300 seconds, with an ETag (`core/http/cached.py`). An API write, an MCP tool write and each batch of a CSV import drop them in every API process (`core.cache.publish`, over Postgres `NOTIFY`). On SQLite, a write from another process shows after the time runs out.

## Known gaps

- Most views in `api.py` and `member_api.py` open their own session and query. The leaderboards, the member list, point adds, the event and entry deletes and the CSV import are in `service.py` and `csv_import.py`. Move the rest one route at a time, with the contract tests.
- The camelCase routes (`getUserPoints`, `getUserTotalPoints`) are aliases. See Cleanup in `docs/roadmap.md`.
