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

`docker-compose.yml` defines both services on a `soda-network` bridge with `restart: unless-stopped`
and JSON log rotation (10 MB × 3 files).

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

`docker-compose.dev.yml` overlays the API service with bind mounts for `modules/`, `main.py` and
`shared.py`, and sets `IS_PROD=false` for hot reload.

## CI — `.github/workflows/check.yml`

Runs on push to `main`/`master` and on every PR:

1. `uv sync`
2. `make check` — ruff lint (`--fix`), ruff format, `ty` type check, pytest, `alembic upgrade head`,
   `alembic check`
3. On PRs only: commits any auto-fixes back to the branch (`git-auto-commit-action`)
4. `bandit -c pyproject.toml -r . -f json` — security scan

Because step 3 pushes to your branch, expect a `style: auto-fix linting and formatting issues`
commit to appear on your PR if you did not run `make check` locally.

Bandit exclusions are configured in `pyproject.toml` (`tests`, `web`, `node_modules`, `.venv`), and
specific known-safe lines are annotated with `# nosec` comments plus a justification.

## CD — `.github/workflows/cd.yml`

Runs on every push to `main`, with `concurrency: cd-production, cancel-in-progress: true` so only one
deploy runs at a time.

It SSHes into the VPS (credentials in repo secrets `VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_PORT`,
`VPS_SSH_PASSWORD`) and runs:

```bash
cd /var/www/soda-internal-api
make discard-local-changes     # git reset --hard
make deploy
make health
```

If `make deploy` fails it dumps `make logs`; if `make health` fails it dumps `make status`.

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
you must reverse that migration yourself (`uv run alembic downgrade -1`).

## Operational recipes

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

Logs are colour-formatted by `colorlog` at INFO. There is a lot of DEBUG-level detail in
`decoraters.py` and `bot.py` that will not appear unless you lower the level in
`modules/utils/logging_config.py`.

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
