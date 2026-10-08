# Operations

This page tells you how to deploy Platform, roll it back, move it to Postgres, turn off routes and run Hermes Agent as an org app. To run Platform on one RunPod pod, see [Getting started](./getting-started.md).

## Compose services

`docker-compose.yml` defines these services. Each one restarts unless stopped and keeps 3 log files of 10 MB.

| Service | Command | Profile |
| --- | --- | --- |
| `api` | `alembic upgrade head`, then gunicorn with 1 worker and 8 threads on port 8000 | default |
| `bot` | `python3 bot_main.py`. Run exactly one, or each scheduled post goes out more than once | default |
| `web` | The static React build on port 5000 | default |
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
| `images.yml` | Builds the API and web images on each PR. On `main` it pushes them to GHCR as `ghcr.io/<owner>/<repo>-api` and `-web` |
| `hermes-image.yml` | Builds `deploy/hermes` when it changes. On `main` it pushes `ghcr.io/<owner>/<repo>-hermes` |
| `cd.yml` | Deploys the example SoDA server after `check.yml` passes on `main`. It runs only in `asusoda/platform` |

`Dockerfile.api` uses `uv sync --frozen`. If `uv.lock` does not agree with `pyproject.toml`, the build fails. Commit the two files together. The web image gets `REACT_APP_API_URL` at build time, so a change to it needs a new build.

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
2. Select the images to build. A change in `web/` or `Dockerfile.web` builds `web`. A change in a compose file or the `Makefile` builds both. A change in `.github/` or a `.md` file builds nothing. All other changes build `api`.
3. Run `uv run alembic upgrade head` on the host. If it fails, the deploy stops and the old containers keep running.
4. Tag the current images as `:previous`.
5. Build and start the changed services, then wait up to 60 seconds for each to be healthy.

## Roll back

`make rollback` tags `soda-internal-api:previous` as `latest` and starts the containers again.

Caution: the rollback does not change the web image or the database. If the failed deploy ran a migration, run `uv run alembic downgrade -1`, or copy back the file that `make backup` wrote to `data/backups/`.

## Move to Postgres

The API reads `DATABASE_URL`. CI runs the tests on SQLite and Postgres 16. Do these steps on a staging server first.

1. Add `POSTGRES_PASSWORD` to `.env`. Start the database: `docker compose --profile postgres up -d postgres`.
2. Make the schema: `DATABASE_URL=postgresql://platform:<password>@localhost:5432/platform uv run alembic upgrade head`.
3. Stop the writers: `docker compose stop api bot`.
4. Copy the data: `uv run python scripts/copy_sqlite_to_postgres.py sqlite:///./data/user.db <postgres url>`. The script refuses tables that have rows. It stops with an error if a row count or an org's points total is different.
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
