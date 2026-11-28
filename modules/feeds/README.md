# feeds

Posts new job listings and hackathons to Discord channels: each feed reads one source on a schedule and posts only new items to its alert destination (`destination_id`, see `modules/alerts`). A feed has a kind: `github_jobs` (the job table of a GitHub README) or `hackathons` (Hack Club, Euro-Hackathons and Hackalist). Each kind belongs to a sub-module: `github_jobs` to [feeds.jobs](submodules/jobs/README.md) and `hackathons` to [feeds.hackathons](submodules/hackathons/README.md). When the org has the module or the kind's sub-module off, those feeds are hidden and do not run. The presets are the `FEEDS` of the sub-modules the org has on. Each post goes through the alerts send path (`modules/alerts/delivery.py`), which logs it in `deliveries` and updates the destination's last result. Other org events go to the same destinations.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Officer routes to create, list, update, delete and run feeds |
| `tools.py` | The `feeds.*` tools for agents |
| `service.py` | Feeds, runs, duplicate checks, and the message of each new item |
| `types.py` | `Item`, `SourceError`, `Feed` (a preset) and the fetch signature of a source |
| `submodules/` | `jobs` and `hackathons`, the shared sub-modules with the presets |
| `github_jobs.py` | The `github_jobs` kind: reads the job table, config checks and the fetch |
| `hackathons.py` | The `hackathons` kind: reads the hackathon listings, config checks and the fetch |
| `models.py` | Feeds, the items each feed posted, and its runs |
| `jobs.py` | The scheduled run and the run on request |

## Surface

- Routes: `/api/feeds/<org>/feeds` and `/api/feeds/<org>/presets`. Officers of the org only. `GET /feeds/<key>/history` returns the runs and items of a feed. `GET /presets` returns the feeds that the org's feeds sub-modules offer.
- Jobs: `feeds.run_due`, schedule `*/15 * * * *`; `feeds.run_feed`, started by the run route. While a run of a feed is queued, the run route returns 409. A run writes the row of an item before it posts the item, so two runs at the same time do not post it twice.
- Tools: `feeds.list`, `feeds.presets`, `feeds.history`, `feeds.save`, `feeds.run`, `feeds.delete` (confirm), all with scope `feeds:manage`. Tools marked confirm run only with `confirm=true`.
- Tables: `alert_feeds` (with `destination_id`), `alert_posts`, `alert_runs`. Secrets: `alert_webhook_<feed key>`, only for a feed made before migration `c6e8a0b2d4f6`.
- Limits: `feeds.feeds` (default 20). See [docs/limits.md](../../docs/limits.md).
- Switches: `feeds`, `feeds.jobs` and `feeds.hackathons`. Migration `a3c5e7f9b1d3` made `feeds` from the `job_webhook` and `hackathon_webhook` switches: on when either was on. Migration `c5e7a9b1d3f4` turned each sub-module on for an org that subscribed to `careers` or had a feed of its kind.

See [docs/modules/feeds.md](../../docs/modules/feeds.md).
