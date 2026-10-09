# Operations

This page tells you how to deploy Platform, roll it back, move it to Postgres, turn off routes and run Hermes Agent as an org app. To run Platform on one RunPod pod, see [Getting started](./getting-started.md).

## Compose services

`docker-compose.yml` defines these services. Each one restarts unless stopped and keeps 3 log files of 10 MB.

| Service | Command | Profile |
| --- | --- | --- |
| `api` | `alembic upgrade head`, then gunicorn with 1 worker and 8 threads on port 8000 | default |
| `bot` | `python3 bot_main.py`. Run exactly one, or each scheduled post goes out more than once | default |
| `dashboard` | The dashboard build (`Dockerfile.dashboard`) on port 5000 | default |
| `postgres` | Postgres 16 with pgvector | `postgres` |
| `worker` | `python3 worker_main.py` | `postgres` |
| `mcp` | `python3 mcp_main.py` on port 8001 | `mcp` |

The API mounts `./data` (SQLite database and JWT keys), `./.env` and `./google-secret.json`.

Caution: make sure that `google-secret.json` is on the host, also if it is empty. If it is not there, the API container does not start.

The API uses one gunicorn worker because the one-time sign-in codes are in process memory. Increase `--workers` only after those codes move to the database.

## Images and CI

| Workflow | Does |
| --- | --- |
| `check.yml` | On each push and PR: `make ci` and bandit; migrations and tests on Postgres 16; the dashboard tests and build |
| `images.yml` | Builds the API and dashboard images on each PR. On `main` it pushes them to GHCR as `ghcr.io/<owner>/<repo>-api` and `-dashboard` |
| `hermes-image.yml` | Builds `deploy/hermes` when it changes. On `main` it pushes `ghcr.io/<owner>/<repo>-hermes` |
| `cd.yml` | Deploys the example SoDA server after `check.yml` passes on `main`. It runs only in `asusoda/platform` |

`Dockerfile.api` uses `uv sync --frozen`. If `uv.lock` does not agree with `pyproject.toml`, the build fails. Commit the two files together. The dashboard image gets `VITE_API_URL` and `VITE_SITE_URL` at build time (repository variables in CI), so a change to them needs a new build.

## Deploy

`cd.yml` connects to the server over SSH and runs these targets in the repo folder:

```bash
make discard-local-changes   # git reset --hard
make backup                  # copy data/user.db to data/backups/, keep the last 14
make deploy
make health
```

If `make deploy` or `make health` fails, it runs `make rollback`.

`make deploy` does these steps:

1. Get `origin/main` and find the changed files.
2. Select the images to build. A change in `dashboard/` or `Dockerfile.dashboard` builds `dashboard`. A change in a compose file or the `Makefile` builds both. A change in `.github/` or a `.md` file builds nothing. All other changes build `api`.
3. Run `uv run alembic upgrade head` on the host. If it fails, the deploy stops and the old containers keep running.
4. Tag the current images as `:previous`.
5. Build and start the changed services, then wait up to 60 seconds for each to be healthy. When it builds `api`, it also starts `bot` again, because the bot uses the same image.

## Roll back

`make rollback` tags `soda-internal-api:previous` as `latest` and starts the containers again.

Caution: the rollback does not change the dashboard image or the database. If the failed deploy ran a migration, run `uv run alembic downgrade -1`, or copy back the file that `make backup` wrote to `data/backups/`.

## Move to Postgres

The API reads `DATABASE_URL`. CI runs the tests on SQLite and Postgres 16. Do these steps on a staging server first.

1. Add `POSTGRES_PASSWORD` to `.env`. Start the database: `docker compose --profile postgres up -d postgres`.
2. Make the schema: `DATABASE_URL=postgresql://platform:<password>@localhost:5432/platform uv run alembic upgrade head`.
3. Stop the writers: `docker compose stop api bot`.
4. Copy the data: `uv run python deploy/copy_sqlite_to_postgres.py sqlite:///./data/user.db <postgres url>`. The script refuses tables that have rows. It stops with an error if a row count or an org's points total is different.
5. Set `DATABASE_URL=postgresql://platform:<password>@postgres:5432/platform` in `.env`. Run `docker compose --profile postgres up -d`. The `worker` service starts and runs the jobs.
6. Keep `data/user.db` for two weeks or more. To go back, remove `DATABASE_URL` and restart.

## Command-line tools

Run these in the API container (`make shell`) or on your machine with the same `.env`:

```bash
flask --app main config check                    # settings, database and migrations; exits non-zero on a fault
flask --app main org list
flask --app main org create --name "Robotics Club" --prefix robotics --guild-id <id> --officer-role-id <id> --off points,storefront
flask --app main org modules robotics --on calendar
flask --app main jobs list
flask --app main jobs run calendar.sync_all
flask --app main jobs run points.import_event_csv -a org_prefix=robotics -a event_name=X -a event_points=5 -a file_content=...
```

`jobs run` runs the job in the shell process, not through the queue. The audit log records it.

## Turn off routes

`DISABLED_ROUTES` is a comma-separated list of path prefixes. If a request path starts with one of them, the API returns the same 404 as an unknown route. The route stays in the code and in `tests/contract/routes.txt`. If `DISABLED_ROUTES` is empty or not set, all routes are on.

Caution: end a folder prefix with `/`. If you do not, `/api/bot` also turns off `/api/botstatus`.

1. Set `DISABLED_ROUTES` in the server's `.env`.
2. Restart the API: `docker compose restart api`. The API reads `.env` when it starts.
3. Make sure that a turned-off path returns 404: `curl -i https://<api host>/api/public/getnextevent`.

The example AIS server sets these prefixes, because the routes are broken:

| Prefix | Fault |
| --- | --- |
| `/api/public/getnextevent` | The view returns no response, so each call returns 500 |
| `/api/bot/` | The game routes read `current_app.auth_bot`, which gunicorn never sets. Some also call `db_connect` methods that do not exist |

```bash
DISABLED_ROUTES=/api/public/getnextevent,/api/bot/
```

## Health, logs and errors

- `GET /health` returns `status`, `commit` and `started_at`. `commit` comes from the `GIT_COMMIT_HASH` build argument, so it shows the image, not the files on disk.
- `make logs` shows the last 50 lines. `make logs-follow` follows them.
- With `LOG_FORMAT=json` (set in compose), each line is a JSON object with `ts`, `level`, `logger`, `msg` and the request fields (`route`, `status`, `org`, `reason`). `LOG_FORMAT=text` gives colored lines.
- If `SENTRY_DSN` is set, Sentry gets errors, logs and a trace of each request (`traces_sample_rate=1.0` in `core/log.py`). If the cost is too high, decrease the sample rates.

Caution: do not delete `data/jwt_private.pem` or `data/jwt_public.pem`. If you delete them, every officer must sign in again.

## Hermes Agent

`deploy/hermes/` runs [Hermes Agent](https://hermes-agent.nousresearch.com) as an org app on RunPod. Hermes talks to members in Discord and uses the org's tools through the MCP server. Any agent that uses MCP connects the same way. See [RunPod apps](./modules/runpod-apps.md) for app manifests and deploys.

| File | Holds |
| --- | --- |
| `Dockerfile` | The official Hermes image at a fixed version, started as `hermes gateway run` |
| `platform-config.sh` | Runs at each start. Writes the model and the Platform MCP server into `/opt/data/config.yaml` and keeps the rest of the file |
| `app.example.json` | The app manifest, with the values to fill in |

1. Run the MCP server where Hermes can reach it. On a pod from [Getting started](./getting-started.md), add `8001/http` to the pod ports.
2. Make a machine token of kind `agent` with the scopes Hermes can use, for example `org:read` and `knowledge:read`. Add `agents:read` and `agents:write` only if Hermes keeps member memories.
3. Make a Discord app and bot for Hermes. It is not the org's Platform bot.
4. Make a RunPod network volume of 10 GB in one data center. Hermes keeps its config, memories, sessions and skills in `/opt/data` on it.
5. Save the org secrets in the table below.
6. Copy `app.example.json` and fill in the volume id, its data center, the MCP URL and the Discord role that can talk to Hermes. Register it with `PUT /api/apps/hermes` and the body `{"manifest": {...}}`.
7. Deploy a tag that the workflow pushed: `POST /api/apps/hermes/deploy` with `{"tag": "<commit sha>"}`. The health check reads `/health` on port 8642.

| Org secret | Value |
| --- | --- |
| `app_hermes_discord_token` | The Hermes Discord bot token |
| `app_hermes_openrouter_key` | The model provider token. Another provider needs its own env name, such as `ANTHROPIC_API_KEY` |
| `app_hermes_platform_token` | The machine token from step 2 |
| `app_hermes_api_key` | A long random string that protects the Hermes API on port 8642 |

The manifest env sets `HERMES_PROVIDER` and `HERMES_MODEL`, `PLATFORM_MCP_URL` and `PLATFORM_TOKEN` (without both, Hermes has no Platform tools), and `DISCORD_ALLOWED_ROLES`, `DISCORD_ALLOWED_USERS` or `DISCORD_ALLOWED_CHANNELS` (set one or more).

Caution: anyone with `API_SERVER_KEY` has full use of the agent, including its terminal. Anyone with access to the org's RunPod account can read the pod env. Revoke the machine token on the dashboard Tokens page to stop Hermes from using Platform.

To keep the memories and skills of a Hermes that runs on a laptop, copy its `~/.hermes` folder to the network volume before the first deploy. Do not copy `.env`; put its secrets in org secrets. When the pod is healthy, stop the old gateway (`systemctl --user stop hermes-gateway`), or the same Discord bot runs two times.

## Agents on the platform pod

To save the cost of more pods, the platform pod can also run Sparky (engine and Discord bot) and Hermes. `deploy/runpod/start.sh` starts each one when its token is set. Each agent restarts 10 seconds after it stops. Both use a hosted model API, so the pod needs no GPU.

| File | Does |
| --- | --- |
| `sparky.sh` | Copies `engine`, `discord` and `sparky.toml` from the public image `SPARKY_IMAGE:SPARKY_TAG` (default `ghcr.io/ashworks1706/sparkyai-rust:main`) to `/workspace/sparky/bin` with `image_files.py`, then runs both with this platform as the store |
| `hermes.sh` | Installs Hermes `HERMES_VERSION` from its source tag to `/workspace/hermes`, writes the model and the MCP server into its config, and runs `hermes gateway run` as the user `hermes` |
| `image_files.py` | Copies files out of a public image without a container runtime. It downloads again only when the image digest changes |

Set these in the pod env, then restart the pod.

| Agent | Variable | Value |
| --- | --- | --- |
| Sparky | `SPARKY_DISCORD__TOKEN`, `SPARKY_DISCORD__GUILD_ID` | The Sparky bot token and the server id |
| Sparky | `SPARKY_PLATFORM__TOKEN` | A machine token of kind `agent` with `agents:read`, `agents:write`, `knowledge:read`, `accounts:link`, `accounts:token` |
| Sparky | `SPARKY_MODEL__BASE_URL`, `SPARKY_MODEL__API_KEY`, `SPARKY_MODEL__NAME` | Any OpenAI-compatible chat API. The summary model is the same unless `SPARKY_SUMMARY__*` is set |
| Sparky | `SPARKY_TAG` | Optional. An image tag (commit sha) in place of `main` |
| Hermes | `HERMES_ENV_DISCORD_BOT_TOKEN` | The Hermes bot token. Hermes gets each `HERMES_ENV_*` variable without the prefix |
| Hermes | `HERMES_ENV_DISCORD_ALLOWED_ROLES` | The Discord roles that can talk to Hermes |
| Hermes | `HERMES_ENV_OPENROUTER_API_KEY`, `HERMES_PROVIDER`, `HERMES_MODEL` | The model provider key, the provider and the model. Another provider needs its own key name, such as `HERMES_ENV_ANTHROPIC_API_KEY` |
| Hermes | `HERMES_PLATFORM_TOKEN` | A machine token of kind `agent`, for example with `org:read` and `knowledge:read`. Hermes uses the MCP server at `http://127.0.0.1:8001/mcp` |

Sparky sends no query vector unless `SPARKY_EMBEDDING__BASE_URL` is set. The platform then embeds each query with the Embeddings integration, so set the Embeddings card to the model that embedded the org's knowledge. The engine listens on `127.0.0.1:8080` only, and `run_sandbox` is off because the pod cannot run containers.

Hermes keeps its config, memories and skills in `/workspace/hermes/home`. To keep those of a Hermes that runs on a laptop, copy its `~/.hermes` folder there before the first start (not `.env`), then `chown -R hermes:hermes /workspace/hermes/home`. Stop the laptop gateway when the pod one runs.

Caution: Hermes can run shell commands on the pod. It runs as the user `hermes` with only its own env, and `/workspace/data` and the platform checkout are closed to it. To remove the shell tools from Discord, set `platform_toolsets.discord` in its `config.yaml`, for example to `[web, vision, skills, todo]`.

### Use your own GPU later

The model settings are URLs, so a GPU changes only the pod env. Run the Sparky RunPod image (`ghcr.io/ashworks1706/sparkyai-runpod`) on a GPU pod with `SPARKY_MODELS_API_KEY` set and port `8000/http` and `8001/http` open. llama-server then serves chat on 8000 and embeddings on 8001 at the pod proxy URLs.

1. On the platform pod, set `SPARKY_MODEL__BASE_URL=https://<gpu pod>-8000.proxy.runpod.net/v1`, `SPARKY_MODEL__API_KEY` to the `SPARKY_MODELS_API_KEY` value, and `SPARKY_MODEL__NAME` to the GGUF name, for example `Qwen/Qwen3-4B-GGUF:Q4_K_M`.
2. Point the Embeddings integration at `https://<gpu pod>-8001.proxy.runpod.net/v1` with the same key. If its model name changes, embed the knowledge again.
3. To give Hermes the same model, set `HERMES_PROVIDER=custom`, `HERMES_BASE_URL` to the chat URL, `HERMES_MODEL`, and the key in `HERMES_ENV_OPENAI_API_KEY`.

Set `SPARKY_POD_ROLE=models` on the GPU pod so it runs only the model servers. Without it the image also runs its own engine and bot, and the same bot token must not run on two pods.
