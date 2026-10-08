# RunPod apps

Deploys an org's own apps (a Discord bot, an agent, a model server) to RunPod pods. An officer registers the app's manifest one time. Then the app's CI deploys each new image tag with a token that can do nothing else. Each org deploys with its own RunPod key and pays for its own pods. [Hermes Agent](../operations.md#hermes-agent) is an example.

## Setup

Officers can do steps 1, 2 and 4 on the dashboard (Settings > Secrets, and the Apps page). The Apps page also deploys, rolls back and deletes.

1. Save the org's RunPod key as the org secret `runpod_api_key`: `PUT /api/organizations/<id>/secrets/runpod_api_key`.
2. Save each secret env value of the app as an org secret with a name that starts with `app_`.
3. Make a machine token with only `apps:deploy` for the app's CI. A script that manages apps needs `apps:read` and `apps:manage`.
4. Register the app in one of two ways:
   - From its repo: `PUT /api/apps/<name>` with `{"repo": "owner/name"}`, and `manifest_path` if the file is not `platform.app.yaml` at the root. Platform reads the file from the default branch now, and again at the `ref` of each deploy. A private repo needs the org secret `github_token` with read access to the repo contents.
   - Inline: `PUT /api/apps/<name>` with `{"manifest": {...}}`.

With a repo, a change to the pod's env, ports or disk is a pull request to the app, with the same review as its code. A person who can merge to the app's repo can already change what runs on the pod. Thus the deploy token gets no more access.

## Manifest

`platform.app.yaml` has the same fields as the inline JSON:

```json
{
  "kind": "bot",
  "description": "The club Discord bot",
  "image": "ghcr.io/example-club/club-bot",
  "gpu": {"id": "NVIDIA RTX A5000", "count": 1},
  "cloud": "SECURE",
  "disk": 50,
  "ports": ["8080/http"],
  "env": {"MODE": "prod"},
  "secret_env": {"DISCORD_TOKEN": "app_club_bot_discord_token"},
  "mounts": {"network": [{"volumeId": "vol_xyz", "path": "/runpod-volume"}]},
  "health": {"port": 8080, "path": "/health"}
}
```

- `kind` is `bot`, `agent`, `site` or `service` (the default). `description` (200 characters or fewer) and `url` (https, the app's public address) are optional. The dashboard groups apps by `kind` and shows the other two. Deploys do not send these three fields to RunPod. App responses include `kind`, `description`, `url` and `host` (`runpod`).
- `image` has no tag. The deploy gives the tag. Use `gpu` or `cpu` (`{"id": "cpu5c", "vcpuCount": 4}`), not both.
- `gpu`, `cpu`, `cloud`, `dataCenterIds` and `mounts` apply when the pod is created. To change them, terminate the pod in RunPod, then `DELETE` and `PUT` the app again.
- `env`, `disk`, `ports`, `args` and `registry` go with each deploy.
- `secret_env` maps a pod env var to an org secret. The deploy reads the values. The API never returns them, and a dry run shows `(secret)`. RunPod shows pod env in its console, so a person with access to the org's RunPod account can read them.
- Platform checks `health` at `https://<pod>-<port>.proxy.runpod.net<path>`. The port must be in `ports` as `/http`.

## Routes

All routes are under `/api/apps`. They need a machine token, and the org is the org of the token.

| Route | Scope | Does |
| --- | --- | --- |
| `GET /` | `apps:read` | Apps with pod id, current tag and latest deployment |
| `GET /<name>` | `apps:read` | One app and its manifest |
| `PUT /<name>` | `apps:manage` | Creates or replaces the manifest |
| `DELETE /<name>` | `apps:manage` | Removes the app record. The pod continues to run |
| `GET /<name>/deployments` | `apps:read` | The latest 20 deployments |
| `GET /<name>/pod` | `apps:read` | The pod as RunPod shows it |
| `POST /<name>/deploy` | `apps:deploy` | `{"tag": "v1.2.0" or "sha256:...", "ref": "<git sha>", "dry_run": false}`. `ref` is only for apps with a repo; without it, Platform reads the default branch. A dry run returns the manifest and the RunPod request. 202 when the deploy starts |
| `POST /<name>/rollback` | `apps:manage` | Deploys the newest healthy tag that is not the current tag, with the manifest of that deploy |

The `apps.list` tool returns the same list as `GET /`.

The first deploy creates the pod, named `<org>-<app>`. A later deploy changes its image, which restarts it: the container disk is erased and volumes stay. A new deploy replaces one that is still in progress. The `runpod.check_deployments` job runs each minute. It marks a deployment healthy when its health path returns a status below 400, or failed after 15 minutes. There is no automatic rollback.

## Deploy from GitHub Actions

Add this step after the image push. For an app with an inline manifest, remove `ref`.

```yaml
- name: Deploy to RunPod
  run: |
    curl -fsS -X POST "$PLATFORM_URL/api/apps/club-bot/deploy" \
      -H "Authorization: Bearer $DEPLOY_TOKEN" -H "Content-Type: application/json" \
      -d "{\"tag\": \"${GITHUB_SHA}\", \"ref\": \"${GITHUB_SHA}\"}"
  env:
    PLATFORM_URL: ${{ vars.PLATFORM_URL }}
    DEPLOY_TOKEN: ${{ secrets.PLATFORM_DEPLOY_TOKEN }}
```
