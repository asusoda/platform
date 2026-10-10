# Hermes Agent

`deploy/hermes/` runs [Hermes Agent](https://hermes-agent.nousresearch.com) from Nous Research as an org app on RunPod. Hermes talks to members in Discord and uses the org's Platform tools (org info, knowledge search, live campus queries and the rest the token allows) over the MCP server. It is an example of running an off-the-shelf agent on Platform; any agent that speaks MCP is set up the same way.

## What is in deploy/hermes

| File | Holds |
| --- | --- |
| `Dockerfile` | The official Hermes image, pinned, started as `hermes gateway run` |
| `platform-config.sh` | Runs on every start. Writes the model and the Platform MCP server into `/opt/data/config.yaml` and keeps the rest of the file |
| `app.example.json` | The app manifest, with the values to fill in |

The `Hermes image` workflow builds the image when `deploy/hermes` changes and pushes it to GHCR on main as `ghcr.io/<owner>/<repo>-hermes`, tagged with the commit sha and `main`. Make the package public in GitHub, or give the manifest a RunPod `registry` credential.

## Setup

1. Run the Platform MCP server where Hermes can reach it. On the RunPod pod from [RunPod deploy](./runpod-deploy.md) it runs on port 8001; add `8001/http` to the pod's ports.
2. Issue a machine token of kind `agent` with the scopes Hermes may use, for example `org:read` and `knowledge:read`. Add `agents:read` and `agents:write` only if Hermes should read and write member memories.
3. Create a Discord application and bot for Hermes. It is a separate bot from the org's Platform bot.
4. Create a RunPod network volume (10 GB is enough) in one data center. Hermes keeps its config, memories, sessions and skills on it at `/opt/data`, so they survive deploys.
5. Store the org secrets the manifest names:

| Org secret | Value |
| --- | --- |
| `app_hermes_discord_token` | Hermes's Discord bot token |
| `app_hermes_openrouter_key` | Model provider key. Another provider needs its own env name, see below |
| `app_hermes_platform_token` | The machine token from step 2 |
| `app_hermes_api_key` | A long random string. It guards the Hermes API on port 8642 |

6. Copy `app.example.json`, fill in the volume id, its data center, the Platform MCP URL and the Discord role allowed to talk to Hermes, then register it: `PUT /api/apps/hermes` with `{"manifest": {...}}`.
7. Deploy a tag the workflow pushed: `POST /api/apps/hermes/deploy` with `{"tag": "<commit sha>"}`. The health check reads `/health` on port 8642.

## Environment

| Name | Meaning |
| --- | --- |
| `HERMES_PROVIDER`, `HERMES_MODEL` | Written to `model.provider` and `model.default`. The provider key goes in its own env var: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `NOUS_API_KEY` and so on |
| `PLATFORM_MCP_URL`, `PLATFORM_TOKEN` | The Platform MCP server and the machine token. Without both, Hermes runs with no Platform tools |
| `DISCORD_BOT_TOKEN` | Hermes's Discord bot |
| `DISCORD_ALLOWED_ROLES`, `DISCORD_ALLOWED_USERS`, `DISCORD_ALLOWED_CHANNELS` | Who Hermes answers. Set at least one |
| `API_SERVER_ENABLED`, `API_SERVER_HOST`, `API_SERVER_KEY` | The Hermes API on port 8642, needed for the health check |

Other Hermes settings (`DISCORD_HOME_CHANNEL`, auto threads and so on) are listed in the Hermes docs and go in `env` the same way.

## Access

- Hermes can call only the tools the machine token's scopes allow. Revoke the token on the dashboard's Tokens page to cut it off.
- The Hermes API on port 8642 gives full use of the agent, including its terminal, to anyone with `API_SERVER_KEY`. Only `/health` answers without it.
- Anyone with access to the org's RunPod account can read the pod's env in the RunPod console.

## Moving an existing Hermes

To keep the memories and skills of a Hermes that runs on a laptop, copy its `~/.hermes` folder to the network volume before the first deploy, for example through a temporary pod with the volume mounted. Leave out `.env` and put its secrets in org secrets instead. Stop the old gateway (`systemctl --user stop hermes-gateway`) once the pod is healthy, so the same Discord bot does not run twice.
