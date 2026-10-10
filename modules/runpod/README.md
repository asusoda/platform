# runpod

Deploys an org's own apps to pods on a hosting provider: register an app's manifest, deploy a new image tag from the app's CI, check health, roll back. Each app keeps its `provider`, and calls go through `core/hosting.py`. RunPod is the only provider, and each org pays with its own RunPod key. The module name stays `runpod`.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Machine routes for apps, deployments, deploy and rollback |
| `service.py` | Manifests (inline, or `platform.app.yaml` from the app's repo), deploys, health checks and rollback on the app's provider; declares `apps:read`, `apps:manage`, `apps:deploy` and the `runpod_api_key`, `github_token` and `app_*` secrets |
| `templates.py` | App templates from `apps/<name>/platform.app.yaml`, and new apps made from them |
| `models.py` | Apps, with their `provider`, and deployments |
| `tools.py` | The `apps.*` tools and `hosting.providers` |
| `jobs.py` | The health check job |

## Surface

- Routes: `/api/apps`, and `/api/apps/templates` for app templates. Machine tokens only, with `apps:read`, `apps:manage` or `apps:deploy`.
- Jobs: `runpod.check_deployments`, schedule `* * * * *`.
- Tools: `apps.list`, `apps.get`, `apps.pod`, `apps.templates`, `hosting.providers` (scope `apps:read`); `apps.register`, `apps.create_from_template`, `apps.delete` (confirm), `apps.rollback` (confirm) (scope `apps:manage`); `apps.deploy` (confirm, scope `apps:deploy`). Without `confirm=true`, deploy and rollback return their dry run. Tools marked confirm run only with `confirm=true`.
- Webhook events: `app.deployed`, when a deploy becomes healthy or fails. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `runpod_apps`, `runpod_deployments`.

See [docs/modules/runpod-apps.md](../../docs/modules/runpod-apps.md).
