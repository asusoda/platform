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
- Tools: `apps.list` (scope `apps:read`).
- Tables: `runpod_apps`, `runpod_deployments`.

See [docs/modules/runpod-apps.md](../../docs/modules/runpod-apps.md).
