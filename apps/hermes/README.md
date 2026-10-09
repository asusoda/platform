# Hermes Agent

[Hermes Agent](https://github.com/NousResearch/hermes-agent) from Nous Research is a Discord agent. It uses the org's Platform tools as an MCP client with a machine token. Platform does not depend on Hermes.

Nous Research publishes the image only to Docker Hub, and Platform does not use Docker Hub images. Thus the template has no image: build one and give its name as the Image input.

## Build the image

1. Build Hermes from its repo at a release tag: `docker build -t hermes-base https://github.com/NousResearch/hermes-agent.git#v2026.9.24`.
2. Build `image/` on top of it: `docker build --build-arg HERMES_IMAGE=hermes-base -t ghcr.io/<owner>/hermes-agent:v2026.9.24 apps/hermes/image`.
3. Push it to GHCR. Make the package public, or add a RunPod `registry` credential to the manifest.

`image/platform-config.sh` runs on each start. It writes the model and the Platform MCP server into `/opt/data/config.yaml`. The image starts `hermes gateway run`.

## Inputs

| Input | Sets |
| --- | --- |
| Image | `image`, without a tag. Deploy the tag you pushed |
| Platform MCP URL | `PLATFORM_MCP_URL`, for example `https://<platform pod>-8001.proxy.runpod.net/mcp` |
| Platform machine token | `PLATFORM_TOKEN`. Issue a token of kind `agent` with only the scopes Hermes needs |
| Discord bot token | `DISCORD_BOT_TOKEN`. Use a bot that is not the Platform bot |
| Discord role IDs | `DISCORD_ALLOWED_ROLES`: the roles that Hermes answers |
| OpenRouter API key | `OPENROUTER_API_KEY`, for `HERMES_MODEL` |
| Hermes API key | `API_SERVER_KEY`. A long random string, for example from `openssl rand -hex 32` |
| Network volume ID, data center | The volume at `/opt/data`: config, memories, sessions and skills |

Secret inputs are saved as org secrets named `app_<name>_<input>`.

## Access

- Hermes can call only the tools of the token's scopes. Revoke the token on the Tokens page to stop it.
- The Hermes API on port 8642 gives full use of the agent to anyone with `API_SERVER_KEY`. Only `/health` answers without it.
- A person with access to the org's RunPod account can read the pod env.
