# RunPod apps (runpod module)

Deploys an org's own apps (a Discord bot, an agent, a model server) to RunPod pods. An officer registers the app's manifest once. After
that, the app's CI deploys each new image tag with a token that can do nothing else. Each org
deploys with its own RunPod API key, so each org pays for its own pods.

[Hermes Agent](./hermes.md) is a worked example.

## Setup

1. Store the org's RunPod key as the org secret `runpod_api_key`
   (`PUT /api/organizations/<id>/secrets/runpod_api_key`).
2. Store each secret env value the app needs as an org secret named `app_...`.
3. Issue a machine token with `apps:read` and `apps:manage` for officers, and one with only
   `apps:deploy` for the app's CI.
4. Register the app, one of two ways:
   - From its repo: `PUT /api/apps/<name>` with `{"repo": "owner/name"}` (and `manifest_path`
     when the file is not `platform.app.yaml` at the root). The file is read from the default
     branch now, and again at each deploy's `ref`. Private repos need the org secret
     `github_token`, a token that can read the repo's contents.
   - Inline: `PUT /api/apps/<name>` with `{"manifest": {...}}`.

With a repo, a change to the pod's env, ports or disk is a pull request to the app, reviewed
like its code. Anyone who can merge to the app's repo can already change what runs on the pod,
so reading the manifest from the same commit gives the deploy token no more reach than that.

## Manifest

The same fields as YAML in `platform.app.yaml`, or as JSON inline:

```json
{
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

- `image` has no tag; the deploy gives it. Exactly one of `gpu` or `cpu` (`{"id": "cpu5c", "vcpuCount": 4}`).
- `gpu`, `cpu`, `cloud`, `dataCenterIds` and `mounts` apply when the pod is created. Changing
  them later means terminating the pod in RunPod and clearing the app (`DELETE`, then `PUT` again).
- `env`, `disk`, `ports`, `args` and `registry` are sent on every deploy.
- `secret_env` maps a pod env var to an org secret. Values are read at deploy time and never
  returned by the API; a dry run shows them as `(secret)`. RunPod shows pod env in its console,
  so anyone with access to the org's RunPod account can read them there.
- `health` is checked at `https://<pod>-<port>.proxy.runpod.net<path>`, so the port must be listed
  in `ports` as `/http`.

## Routes

All under `/api/apps`, machine tokens only, org from the token.

| Method and path | Scope | Does |
|---|---|---|
| `GET /` | apps:read | Apps with pod id, current tag, latest deployment |
| `GET /<name>` | apps:read | One app with its manifest |
| `PUT /<name>` | apps:manage | Create or replace the manifest |
| `DELETE /<name>` | apps:manage | Forget the app. The pod keeps running |
| `GET /<name>/deployments` | apps:read | Latest 20 deployments |
| `GET /<name>/pod` | apps:read | The pod as RunPod reports it |
| `POST /<name>/deploy` | apps:deploy | `{"tag": "v1.2.0" or "sha256:...", "ref": "<git sha>", "dry_run": false}`. `ref` only for apps with a repo; omitted, the default branch is read. A dry run returns the manifest and the RunPod request. 202 when started |
| `POST /<name>/rollback` | apps:manage | Deploy the newest healthy tag other than the current one, with the manifest that deploy used |

`apps.list` is the same listing as an MCP tool.

The first deploy creates the pod (named `<org>-<app>`). Later deploys change its image, which
restarts it: container disk is wiped, volumes stay. A newer deploy replaces one still running.
The `runpod.check_deployments` job runs every minute and marks a deployment healthy when its
health path answers below 400, or failed after 15 minutes. There is no automatic rollback.

## Deploying from GitHub Actions

After the image is pushed. Drop `ref` for an app registered with an inline manifest:

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
