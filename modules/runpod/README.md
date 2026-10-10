# runpod

Deploys an org's own apps to RunPod pods: register an app's manifest, deploy a new image tag from the app's CI, check health, roll back. Each org pays with its own RunPod key.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Machine routes for apps, deployments, deploy and rollback |
| `service.py` | Manifests (inline, or `platform.app.yaml` from the app's repo), deploys, health checks and rollback; declares `apps:read`, `apps:manage`, `apps:deploy` and the `runpod_api_key`, `github_token` and `app_*` secrets |
| `models.py` | Apps and deployments |
| `tools.py` | The `apps.list` tool |
| `jobs.py` | The health check job |

## Surface

- Routes: `/api/apps`. Machine tokens only, with `apps:read`, `apps:manage` or `apps:deploy`.
- Jobs: `runpod.check_deployments`, schedule `* * * * *`.
- Tools: `apps.list`, `apps.get` (scope `apps:read`); `apps.register`, `apps.delete` (confirm), `apps.rollback` (confirm) (scope `apps:manage`); `apps.deploy` (confirm, scope `apps:deploy`). Without `confirm=true`, deploy and rollback return their dry run. Tools marked confirm run only with `confirm=true`.
- Webhook events: `app.deployed`, when a deploy becomes healthy or fails. See [docs/webhooks.md](../../docs/webhooks.md).
- Tables: `runpod_apps`, `runpod_deployments`.

See [docs/modules/runpod-apps.md](../../docs/modules/runpod-apps.md).
