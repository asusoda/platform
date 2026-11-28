# points.checkins

A sub-module of `points`, switch `points.checkins`. Gives event points to each member who checked in on an attendance CSV.

## Files

| File | Holds |
| --- | --- |
| `csv_import.py` | The attendance CSV import: the upload checks (`queue_upload()`), the run row, the parse, the award in batches of 25 rows, and `changed()`, which drops the org's cached reads in every process |
| `jobs.py` | The CSV import job |
| `tools.py` | The `points.import_csv` tool |

## Surface

- Routes: `POST /api/points/<org_prefix>/uploadEventCSV` returns 202 with `import_id`. It needs this switch and `points`. The import runs are read with `GET /api/points/<org_prefix>/imports` and the `points.imports` tool of `points`.
- Jobs: `points.import_event_csv`, started by the CSV upload, once for each `import_id`. A job with no `import_id` (queued by an older API) runs with no run row.
- Tools: `points.import_csv` (scope `points:write`).
- Tables: none of its own. Runs are in `points_imports` of `points`.
