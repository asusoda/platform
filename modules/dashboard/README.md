# dashboard

Routes for the officer dashboard in `dashboard/`: one overview of all that the org runs, the org's branding, the latest GitHub Actions runs for the repos the org lists, the org's errors, and officer control of apps and knowledge sources.

## Files

| File | Holds |
| --- | --- |
| `service.py` | The overview: problems, module switches, activity, job runs and a section for each module |
| `trends.py` | Daily counts for the Overview charts: actions, job runs, points, store orders, agent questions, knowledge runs and alert posts |
| `notices.py` | Notifications: the org's current problems, and which ones officers marked resolved |
| `errors.py` | The org's errors from `core/error_log.py`: list, resolve, reopen, reports from the dashboard, the Discord alert webhook, and `setup()` that each process calls at start |
| `ci.py` | The org's repo list and its GitHub Actions runs, in a cache for 120 seconds |
| `api.py` | Officer routes for the overview, branding, CI runs and the repo list; officer routes that call the `runpod` and `knowledge` services |
| `tools.py` | Tools for the overview, trends, notifications, errors, audit log and integrations |

## Surface

- Routes: `/api/dashboard/<org>/overview`, `/trends?days=7..90`, `/notifications`, `/notifications/resolve`, `/notifications/reopen`, `/errors?status=open|resolved|all`, `/errors/resolve`, `/errors/reopen`, `/errors/report`, `/errors/webhook`, `/ci`, `/ci/repos`, `/branding`, `/apps/...` and `/knowledge/...`. Officers of the org only. The apps and knowledge routes are the same operations as the machine routes in those modules, without a token scope.
- Jobs: none.
- Tools: `org.overview`, `org.trends`, `notifications.list`, `errors.list`, `activity.log` (scope `activity:read`); `notifications.resolve`, `notifications.reopen`, `errors.resolve` (scope `settings:write`); `integrations.list`, `integrations.save` (confirm), `integrations.test` (scope `integrations:manage`). Secret values are never returned. Tools marked confirm run only with `confirm=true`.
- Tables: none here. Errors are in `error_groups` (`core/error_log.py`). The repo list is `dashboard.repos`, the resolved notifications are `dashboard.resolved`, and the branding is `branding` in the org config. The optional org secret `github_token` reads private repos. The optional org secret `error_webhook_url` is the Discord webhook for error alerts.

See [docs/frontends.md](../../docs/frontends.md).
