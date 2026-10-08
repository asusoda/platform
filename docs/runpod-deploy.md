# Running the platform on a RunPod pod

`deploy/runpod/start.sh` runs the whole platform on one CPU pod. RunPod pods run one image and no
docker, so the script installs and starts everything in the pod itself:

- API (gunicorn) on port 8000, web app on port 5000, Discord bot when `BOT_TOKEN` is set.
- Jobs run in threads of the API (SQLite).
- On each start it fetches `PLATFORM_BRANCH`, so a pod restart deploys the branch head.
- State is in `/workspace/data` on a network volume: the SQLite database and `keys.env`, which
  holds `SECRET_KEY` and `SECRETS_KEY` generated on first boot. Losing `keys.env` makes stored
  org secrets unreadable.

## Pod settings

Image `nikolaik/python-nodejs:python3.12-nodejs20`, ports `8000/http` and `5000/http`, a network
volume at `/workspace`, and this start command:

```
bash -c "curl -fsSL https://raw.githubusercontent.com/theaisocietyasu/bedrock/$PLATFORM_BRANCH/deploy/runpod/start.sh | bash"
```

Environment:

| Name | Value |
|------|-------|
| `PLATFORM_BRANCH` | Branch to run |
| `ORG_PREFIX`, `ORG_NAME`, `ORG_GUILD_ID`, `ORG_OFFICER_ROLE_ID`, `ORG_MODULES_OFF` | The org created on first boot |
| `CLIENT_ID`, `CLIENT_SECRET` | Discord OAuth app for officer login |
| `BOT_TOKEN` | Discord bot of the org's server |
| `SYS_ADMIN` | Discord user id of the superadmin |
| `API_URL`, `WEB_URL` | Only with a custom domain; default to the pod's RunPod proxy URLs |

Add `<API_URL>/api/auth/callback` as a redirect in the Discord app. With the proxy URLs that is
`https://<pod id>-8000.proxy.runpod.net/api/auth/callback`.
