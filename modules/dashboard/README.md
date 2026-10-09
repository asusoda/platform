# dashboard

Routes for the officer dashboard in `dashboard/`: one overview of all that the org runs, the org's branding, the latest GitHub Actions runs for the repos the org lists, and officer control of apps and knowledge sources.

## Files

| File | Holds |
| --- | --- |
| `service.py` | The overview: problems, module switches, activity, job runs and a section for each module |
| `trends.py` | Daily counts for the Overview charts: actions, job runs, points, store orders, agent questions, knowledge runs and alert posts |
| `notices.py` | Notifications: the org's current problems, and which ones officers marked resolved |
| `ci.py` | The org's repo list and its GitHub Actions runs, in a cache for 120 seconds |
| `api.py` | Officer routes for the overview, branding, CI runs and the repo list; officer routes that call the `runpod` and `knowledge` services |

## Surface

- Routes: `/api/dashboard/<org>/overview`, `/trends?days=7..90`, `/notifications`, `/notifications/resolve`, `/notifications/reopen`, `/ci`, `/ci/repos`, `/branding`, `/apps/...` and `/knowledge/...`. Officers of the org only. The apps and knowledge routes are the same operations as the machine routes in those modules, without a token scope.
- Jobs: none.
- Tools: none.
- Tables: none. The repo list is `dashboard.repos`, the resolved notifications are `dashboard.resolved`, and the branding is `branding` in the org config. The optional org secret `github_token` reads private repos.

See [docs/frontends.md](../../docs/frontends.md).
