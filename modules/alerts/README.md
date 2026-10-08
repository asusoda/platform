# alerts

Posts new job listings and upcoming hackathons to an org's Discord channels through webhooks. Each feed reads one source on a schedule and posts only new items.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to create, list, update, delete and run feeds |
| `service.py` | Feeds, runs, duplicate checks and Discord webhook posts |
| `jobs_table.py`, `hackathons.py` | The sources: the job table in a GitHub README; Hack Club, Euro-Hackathons and Hackalist |
| `types.py` | `Item`, `SourceError` and the fetch signature of a source |
| `models.py` | Feeds, the items each feed posted, and its runs |
| `jobs.py` | The scheduled run and the run on request |

## Surface

- Routes: `/api/alerts/<org>/feeds`, behind the `alerts` switch. Officers of the org only. `GET /feeds/<key>/history` returns the runs and items of a feed.
- Jobs: `alerts.run_due`, schedule `*/15 * * * *`; `alerts.run_feed`, started by the run route.
- Tools: none.
- Tables: `alert_feeds`, `alert_posts`, `alert_runs`. Secrets: `alert_webhook_<feed key>`.

See [docs/modules/alerts.md](../../docs/modules/alerts.md).
