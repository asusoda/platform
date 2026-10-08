# dashboard

Read-only routes for the officer dashboard in `dashboard/`: one overview of all that the org runs, the org's branding, and the latest GitHub Actions runs for the repos the org lists.

## Files

| File | Holds |
| --- | --- |
| `service.py` | The overview: problems, module switches, activity, job runs and a section for each module |
| `ci.py` | The org's repo list and its GitHub Actions runs, in a cache for 120 seconds |
| `api.py` | Officer routes for the overview, branding, CI runs and the repo list |

## Surface

- Routes: `/api/dashboard/<org>/overview`, `/ci`, `/ci/repos` and `/branding`. Officers of the org only.
- Jobs: none.
- Tools: none.
- Tables: none. The repo list is `dashboard.repos` and the branding is `branding` in the org config. The optional org secret `github_token` reads private repos.

See [docs/frontends.md](../../docs/frontends.md).
