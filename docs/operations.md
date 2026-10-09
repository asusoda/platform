# Operations

This page tells you how to deploy Platform, roll it back, move it to Postgres, and turn off routes. To run Platform on one RunPod pod, see [Getting started](./getting-started.md).

## Compose services

`docker-compose.yml` defines these services. Each one restarts unless stopped and keeps 3 log files of 10 MB.

| Service | Command | Profile |
| --- | --- | --- |
| `api` | `alembic upgrade head`, then gunicorn with 1 worker and 8 threads on port 8000 | default |
| `bot` | `python3 bot_main.py`. Run exactly one, or each scheduled post goes out more than once | default |
| `dashboard` | The dashboard build (`Dockerfile.dashboard`) on port 5001 | default |
| `web` | The old officer app (`Dockerfile.web`) on port 5000, for admin.thesoda.io | default |
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
| `images.yml` | Builds the API, web and dashboard images on each PR. On `main` it pushes them to GHCR as `ghcr.io/<owner>/<repo>-api`, `-web` and `-dashboard` |
| `cd.yml` | Deploys the example SoDA server after `check.yml` passes on `main`. It runs only in `asusoda/platform` |

`Dockerfile.api` uses `uv sync --frozen`. If `uv.lock` does not agree with `pyproject.toml`, the build fails. Commit the two files together. The dashboard image gets `VITE_API_URL` and `VITE_SITE_URL` at build time (repository variables in CI), so a change to them needs a new build.

## Deploy

`cd.yml` connects to the server over SSH and runs these commands in the repo folder:

```bash
DEPLOY_FROM="$(git rev-parse HEAD)"          # the commit that runs now
git fetch origin main && git checkout main && git reset --hard origin/main
make backup                                  # copy data/user.db to data/backups/, keep the last 14
make deploy DEPLOY_FROM="$DEPLOY_FROM"
make health
```

`cd.yml` updates the checkout before `make backup`. Thus the server uses the `Makefile` of the new commit, also when the old `Makefile` has no `backup` target. If `make deploy` or `make health` fails, `cd.yml` runs `make rollback`.

`make deploy` does these steps:

1. Get `origin/main` and find the files changed since `DEPLOY_FROM`. If `DEPLOY_FROM` is empty, it uses the commit that was checked out before the fetch.
2. Select the images to build. A change in `web/` or `Dockerfile.web` builds `web`. A change in `dashboard/` or `Dockerfile.dashboard` builds `dashboard`. A change in a compose file or the `Makefile` builds all three. A change in `.github/` or a `.md` file builds nothing. All other changes build `api`.
3. Tag the current images as `:previous`.
4. Build the changed images. The old containers keep running during the build.
5. Run `uv run alembic upgrade head` on the host. If it fails, the deploy stops and the old containers keep running.
6. Start the changed services with `up -d --remove-orphans`, then wait up to 60 seconds for each to be healthy. When it builds `api`, it also starts `bot` again, because the bot uses the same image. `--remove-orphans` removes containers of services that are no longer in `docker-compose.yml`, so an old container does not keep a port.

Caution: set `VITE_API_URL` in `.env` before you build the dashboard. If it is empty, `Dockerfile.dashboard` stops the build and the deploy fails.

## Upgrade an existing deployment

Do the first deploy after a large upgrade by hand. For an upgrade from `asusoda/platform` at `579a6a84` or older, do these steps on the server:

1. Pause CD, or do the deploy before the next push to `main`.
2. Run `make backup`. If the old `Makefile` has no `backup` target, copy `data/user.db` to `data/user.db.pre-upgrade`. Keep `data/jwt_*.pem`.
3. Run `uv run alembic current`. The result must be `a1b2c3d4e5f6`, the last SoDA migration.
4. Add `VITE_API_URL` to `.env`, for example `https://api.thesoda.io`. Keep `REACT_APP_API_URL` for `web/`.
5. If the database has no `alembic_version` table (`create_all` made it), run `uv run alembic stamp a1b2c3d4e5f6`. If you do not, `alembic upgrade head` stops with "table already exists".
6. Keep the current commit for a rollback: `OLD=$(git rev-parse HEAD)`.
7. Run `git fetch origin main`, then `git reset --hard origin/main`.
8. Run `make deploy DEPLOY_FROM="$OLD"`. If `DEPLOY_FROM` is not set, `make deploy` finds no changed files and builds nothing.
9. Run `flask --app main config check` in the API container. It must show `migrations at head` and no `FAIL`.

LeetCode: the API now posts the daily question as a job and keeps the "posted today" record in the `leetcode_daily` table. If you deploy after `LEETCODE_DAILY_TIME` on a day that already had a post, the channel gets a second post. Deploy before that time to prevent it.

## Roll back

`make rollback` tags `soda-internal-api:previous` as `latest` and starts the containers again.

Caution: the rollback does not change the dashboard image or the database. If the failed deploy ran a migration, run `uv run alembic downgrade -1`, or copy back the file that `make backup` wrote to `data/backups/`.

Caution: `make rollback` alone does not work across the upgrade from `a1b2c3d4e5f6`. Migration `b7d9f1a3c5e8` renames `users.asu_id` to `student_id`, and the old image has no `alembic/` folder. To go back:

1. Run `uv run alembic downgrade a1b2c3d4e5f6`, or copy the backup back to `data/user.db`.
2. Check out the old commit: `git checkout "$OLD"`.
3. Run `make build`, then `make up`.

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
flask --app main org create --name "Robotics Club" --prefix robotics --guild-id <id> --officer-role-id <id> --on points,storefront
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
- If `SENTRY_DSN` is set, the API, bot, job worker and MCP server send errors to Sentry, with a `service` tag (`api`, `bot`, `worker`, `mcp`) and the commit as the release. They also send log lines at `SENTRY_LOGS_LEVEL` (default `WARNING`) and above, and traces for `SENTRY_TRACES_SAMPLE_RATE` of requests (default `0.1`). `SENTRY_PROFILES_SAMPLE_RATE` (default `0`) turns on profiles. `SENTRY_ENVIRONMENT` (default `production`) names the environment.
- Platform keeps its own error log, with no outside service. Each process (`api`, `bot`, `worker`, `mcp`) records every log line at ERROR or above in the `error_groups` table, with the stack trace, the org and the route. The dashboard sends browser errors and API calls that got no answer or a status of 500 or more. Repeats of one error add to one group.
- Officers see their org's errors on Activity, Errors, and resolve them there. The tab only shows errors. A resolved error opens again when it happens again. The superadmin page shows the errors of every org and the errors with no org, such as a failed job.
- Discord alerts: an officer adds a webhook with the Errors event on Automations, Webhooks. See [Webhooks](./webhooks.md). `ERROR_WEBHOOK_URL` in `.env` gets every new error of every org and of the server. Each new or returning error posts one message, at most 30 for each process in an hour.
- Sentry is optional. Set `SENTRY_DSN` only if you want Sentry in addition to the error log.

Caution: do not delete `data/jwt_private.pem` or `data/jwt_public.pem`. If you delete them, every officer must sign in again.
