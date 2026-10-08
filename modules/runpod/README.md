# runpod

Deploys an organization's own apps to RunPod pods: register an app's manifest, deploy a new image tag from the app's CI, check health, roll back. Each org pays with its own RunPod key.

## Files

| File | Holds |
| --- | --- |
| `api.py` | Machine routes for apps, deployments, deploy and rollback |
| `service.py` | Manifests (or `platform.app.yaml` read from the app's repo), deploys, health checks, rollback; declares the `apps:read`, `apps:manage` and `apps:deploy` scopes and the `runpod_api_key`, `github_token` and `app_*` secrets |
| `models.py` | Apps and deployments |
| `tools.py` | The `apps.list` tool |
| `jobs.py` | The health check job |

## Surface

- Routes: `/api/apps`, no module switch. Machine tokens only, with `apps:read`, `apps:manage` or `apps:deploy`; the org is the token's.
- Jobs: `runpod.check_deployments`, cron `* * * * *`.
- Tools: `apps.list` (scope `apps:read`).
- Tables: `runpod_apps`, `runpod_deployments`.

## More

[docs/runpod-apps.md](../../docs/runpod-apps.md)
