# 9. Deployment & Operations

## Where it runs

A single VPS at `/var/www/soda-internal-api`, running two containers under
Podman (or Docker — the Makefile detects whichever is installed). Public hostnames:

- `https://api.thesoda.io` → the API container (port 8000)
- `https://admin.thesoda.io` → the web container (port 5000)

Reverse proxy / TLS termination lives outside this repository.

## Images

### `Dockerfile.api` — multi-stage

```
Stage 1 (builder): python:3.12-slim
  install build-essential, python3-dev, curl
  copy the uv binary from ghcr.io/astral-sh/uv
  COPY pyproject.toml uv.lock       ← copied first so deps cache independently of source
  uv sync --frozen

Stage 2 (runtime): python:3.12-slim
  install curl only (needed by the healthcheck)
  create non-root user `appuser`, mkdir /app/data
  copy /app/.venv from the builder, put it on PATH
  ENV GIT_COMMIT_HASH=${COMMIT_HASH}   ← build arg, surfaced by /health
  copy modules/ and *.py
  USER appuser
  CMD ["python3", "main.py"]
```

`--frozen` means the build fails if `uv.lock` is out of date with `pyproject.toml`. Always commit
both together.

### `Dockerfile.web` — multi-stage

```
Stage 1: node:18-alpine, pnpm 10.10.0 via corepack
  pnpm install --frozen-lockfile
  ARG REACT_APP_API_URL      ← baked into the bundle here
  pnpm run build

Stage 2: node:18-alpine
  pnpm add -g serve, non-root appuser
  copy build/ from stage 1
  CMD ["serve", "-s", "build", "-l", "5000"]
```

## Compose

`docker-compose.yml` defines these services on a `soda-network` bridge with `restart: unless-stopped`
and JSON log rotation (10 MB × 3 files):

- `api`: gunicorn serving `main:app` with one worker and 8 threads. One worker because SQLite takes
  one writer at a time and login codes are held in memory; raise it after the move to Postgres.
  `RUN_BOT_IN_API=false`.
- `bot`: `python3 bot_main.py`, the Discord bot (LeetCode daily post, helper and game cogs), from the
  same image. Exactly one must run, or scheduled posts go out more than once.
- `web`: the static React bundle.
- `postgres` and `worker` (profile `postgres`, off by default): the database and the job worker
  (`python3 worker_main.py`). With SQLite the API runs jobs itself and the worker is not needed.

The game control routes (`/api/bot/*`) call the bot's cogs directly, so with the bot in its own
process they return 503. The web app's game screens already called the wrong paths. Phase 3 moves
the games into their own module.

The API container mounts three things from the host:

```yaml
- ./data:/app/data                        # SQLite DB + JWT keypair (read-write)
- ./.env:/app/.env:ro                     # secrets
- ./google-secret.json:/app/google-secret.json:ro   # Google service account
```

**`google-secret.json` must exist on the host**, even empty, or the container will fail to start on
a missing bind-mount source.

Healthchecks: API polls `curl -f http://localhost:8000/health`; web polls `wget --spider
http://localhost:5000`. Both: 10s interval, 5s timeout, 5 retries, 10s start period.

`docker-compose.dev.yml` runs the API with `python3 main.py` (Flask's reloader) instead of gunicorn,
adds bind mounts for `modules/`, `main.py`, `shared.py` and `bot_main.py`, and sets `IS_PROD=false`.
Running `python3 main.py` outside compose still starts the bot in a thread unless
`RUN_BOT_IN_API=false`.

## CI — `.github/workflows/check.yml`

Runs on push to `main`/`master`, on every PR, and on demand:

1. `uv sync --frozen`
2. `make ci` — ruff lint, ruff format check, `ty` type check, pytest (including the API contract
   tests in `tests/contract/`), then `alembic upgrade head` and `alembic check` against a fresh
   temporary database
3. `bandit -c pyproject.toml -r .` — security scan

Nothing is fixed or committed by CI. Run `make check` locally to auto-fix lint and formatting before
pushing. Make the Check workflow a required status check on `main` in the branch protection settings
so a red run blocks the merge.

Bandit exclusions are configured in `pyproject.toml` (`tests`, `web`, `node_modules`, `.venv`), and
specific known-safe lines are annotated with `# nosec` comments plus a justification.

The contract tests and the endpoints they guard are described in [API Contract](./api-contract.md).

## Images — `.github/workflows/images.yml`

Builds the API and web images on every PR, so a broken Dockerfile fails before merge. On `main` it
pushes them to GHCR as `ghcr.io/<owner>/<repo>-api` and `-web`, tagged with the commit sha and `main`.
The web image bakes in the repository variable `REACT_APP_API_URL`.

## CD — `.github/workflows/cd.yml`

Runs only in `asusoda/platform` (never in forks), only after the Check workflow has passed on a push
to `main`, one deploy at a time.

It SSHes into the VPS (repo secrets `VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_PORT`, and `VPS_SSH_KEY`
for a deploy key, with `VPS_SSH_PASSWORD` kept as a fallback until the key is set) and runs:

```bash
cd /var/www/soda-internal-api
make discard-local-changes     # git reset --hard
make backup                    # copy data/user.db to data/backups/, keep the last 14
make deploy
make health
```

If `make deploy` or `make health` fails, it prints logs or status and runs `make rollback`.

### What `make deploy` actually does

1. Record `OLD_HEAD`, `git fetch origin main`, `git checkout main`, `git reset --hard origin/main`,
   record `NEW_HEAD`.
2. Diff the two to get changed files, then decide **what to rebuild**:
   - `web/*` or `Dockerfile.web` → rebuild **web**
   - `docker-compose*.yml`, `Makefile` → rebuild **both**
   - `.github/*`, any `*.md`, `.pre-commit-config.yaml` → rebuild **nothing**
   - anything else → rebuild **api**
3. `mkdir -p data`, `chmod -R 755 data`, `chown -R 1000:1000 data` (uid 1000 is `appuser` in the
   container).
4. **`uv run alembic upgrade head`** — migrations run on the host, against the same
   `./data/user.db`, *before* the new containers come up. If migrations fail, the deploy aborts and
   the old containers keep running.
5. Tag the current images as `:previous` (this is what enables rollback).
6. Build and `up -d` only the changed services.
7. Poll `podman/docker inspect` for `healthy` (or `running`), up to 60 seconds per container.
8. Print status and the last 20 log lines, then `image prune -f`.

### Rollback

```bash
make rollback
```

Tags the current `soda-internal-api:latest` as `rollback-<timestamp>`, promotes
`soda-internal-api:previous` back to `latest`, and re-ups. It **only rolls back the API image**, not
the web image, and **it does not roll back the database** — if the failed deploy ran a migration,
you must reverse that migration yourself (`uv run alembic downgrade -1`) or restore the copy that
`make backup` wrote to `data/backups/` just before the deploy.

## Moving to Postgres

The app reads `DATABASE_URL` (default `sqlite:///./data/user.db`). The schema comes from Alembic
migrations only: the API container runs `alembic upgrade head` before gunicorn starts, and nothing
calls `create_all` at startup. CI runs the tests and `alembic check` on both SQLite and Postgres 16.

Steps, rehearsed on staging first:

1. Add `POSTGRES_PASSWORD` to `.env` and start the database: `docker compose --profile postgres up -d postgres`.
2. Create the schema: `DATABASE_URL=postgresql://platform:<password>@localhost:5432/platform uv run alembic upgrade head`
   (expose the port or run it inside the network).
3. Stop writers: `docker compose stop api bot`.
4. Copy and verify: `uv run python scripts/copy_sqlite_to_postgres.py sqlite:///./data/user.db <postgres url>`.
   It refuses non-empty tables and exits non-zero if any table's row count or any org's points
   total differs.
5. Set `DATABASE_URL=postgresql://platform:<password>@postgres:5432/platform` in `.env` and
   `docker compose --profile postgres up -d`. The API's `alembic upgrade head` creates the job
   queue tables, and the `worker` service starts running jobs.
6. Keep `data/user.db` for at least two weeks. Rollback is removing `DATABASE_URL` and restarting.

Keep gunicorn at one worker until the switch; afterwards raise `--workers` in `docker-compose.yml`
once login codes move to the database (they are in memory today).

## Operational recipes

### Command-line tools

Run inside the API container (`make shell`) or locally with the same `.env`:

```bash
flask --app main config check     # required settings, database, migrations; non-zero exit on failure
flask --app main org list
flask --app main org create --name "Robotics Club" --prefix robotics --guild-id <discord server id> \
    --officer-role-id <role id> --off points,storefront,calendar
flask --app main org modules robotics --on calendar
flask --app main jobs list
flask --app main jobs run calendar.sync_all
flask --app main jobs run points.import_event_csv -a org_prefix=soda -a event_name=X -a event_points=5 -a file_content=...
```

`jobs run` runs the job in the shell's process, not through the queue, and records it in the audit
log like any other run.

### Which build is live?

```bash
curl -s https://api.thesoda.io/health
# {"status":"healthy","service":"soda-internal-api","commit":"<sha>","started_at":"..."}
```

The `commit` field comes from the `GIT_COMMIT_HASH` build arg, so it identifies the **image**, not
the checkout on disk.

### Logs

```bash
make logs           # last 50 lines, both services
make logs-follow    # tail
```

In compose, `LOG_FORMAT=json` makes every line a JSON object (`ts`, `level`, `logger`, `msg`, and
for request and access lines their `key=value` fields, such as `route`, `status`, `org` and
`reason`). Without it, logs are colour-formatted by `colorlog` at INFO; the dev override sets
`LOG_FORMAT=text`. There is a lot of DEBUG-level detail in
`decoraters.py` and `bot.py` that will not appear unless you lower the level in
`core/logging_config.py`.

### Shell into the API

```bash
make shell          # compose exec api /bin/bash
```

### Database

The database is the file `./data/user.db` on the host. To back it up, stop writes and copy the file
(plus `-wal`/`-shm` if present). There is no dump/restore tooling in this repo.

The JWT signing keys are in the same directory (`jwt_private.pem`, `jwt_public.pem`). **Deleting
them invalidates every access and refresh token in circulation** — everyone gets logged out.

### Migrations in production

They run automatically as step 4 of `make deploy`. To run one by hand on the VPS:

```bash
cd /var/www/soda-internal-api
uv run alembic upgrade head
```

Note this runs on the **host**, not inside the container, using the host's `uv` environment.

## Monitoring

Sentry, if `SENTRY_DSN` is set. Configured in `shared.py` with the Flask integration,
`traces_sample_rate=1.0`, `profiles_sample_rate=1.0`, and `enable_logs=True` — so **every**
transaction is traced and log records ship to Sentry. That is expensive at volume; if the Sentry
bill becomes a problem, those sample rates are the first dial to turn.

The calendar module adds its own Sentry spans through `operation_span` in
`modules/calendar/utils.py` and tags errors through `APIErrorHandler` in `modules/calendar/errors.py`.
