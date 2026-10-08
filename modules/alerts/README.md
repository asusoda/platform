# alerts

Posts new job listings and upcoming hackathons to the organization's Discord channels through webhooks. Each feed reads one source on a schedule and posts only items it has not posted before.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to create, list, update, delete and run feeds |
| `service.py` | Feed storage, runs, deduplication and Discord webhook posts |
| `jobs_table.py` | Reads the job table in a GitHub repository's README |
| `hackathons.py` | Reads Hack Club, Euro-Hackathons and Hackalist listings |
| `types.py` | `Item`, `SourceError` and the fetch signature shared by the sources |
| `models.py` | Feeds and the items each feed has posted |
| `jobs.py` | The scheduled run and the on-request run |

## Surface

- Routes: `/api/alerts/<org>/feeds`, gated by the `alerts` switch. Officers of the org only.
- Jobs: `alerts.run_due`, cron `*/15 * * * *`; `alerts.run_feed`, queued by the run route.
- Tools: none.
- Tables: `alert_feeds`, `alert_posts`.
- Secrets: `alert_webhook_<feed key>`, the Discord webhook URL, encrypted with `SECRETS_KEY`.

## Depends on

`core.secrets`, `core.errors`, `core.jobs`, `core.logging_config`, `core.base`; `modules.auth.routes`, `modules.organizations`; `shared`.

## More

[docs/alerts.md](../../docs/alerts.md)
