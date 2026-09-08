# 1. Getting Started

## What you need installed

| Tool | Why | Install |
|------|-----|---------|
| **uv** | Python dependency + virtualenv manager. Replaces pip/venv/poetry. | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Podman + podman-compose** (or Docker + Docker Compose) | Runs the two containers. The Makefile auto-detects which one you have. | `brew install podman podman-compose` |
| **make** | Every workflow is a make target. | Ships with macOS dev tools |
| **Node 18 + pnpm** | Only if you want to run the React app outside a container. | `corepack enable && corepack prepare pnpm@10.10.0 --activate` |

Python must be **3.12.x** (`requires-python = ">=3.12,<3.13"` in `pyproject.toml`). `uv` will fetch
the right version for you.

## First-time setup

```bash
git clone https://github.com/asusoda/platform.git
cd platform

# 1. Install Python deps into .venv and install the pre-commit hook
uv sync
uv run pre-commit install

# 2. Create your environment file
cp .env.template .env
#    then open .env and fill in the blanks (see the table below)

# 3. Start everything
make dev
```

After `make dev`:

- API → <http://localhost:8000> (health check at `/health`)
- Web → <http://localhost:5000>

`make dev` runs `docker-compose.yml` overlaid with `docker-compose.dev.yml`, which bind-mounts
`modules/`, `main.py` and `shared.py` into the API container and sets `IS_PROD=false`. `IS_PROD=false`
turns on the Flask debugger and the auto-reloader, so Python edits take effect without a rebuild.

## Environment variables

All of these live in `.env` at the repo root. `modules/utils/config.py` reads them into a single
`Config` object; almost every one has a harmless default so the app boots even with an incomplete
`.env` (features just get disabled).

### You will not get far without these

| Variable | What it is |
|----------|-----------|
| `BOT_TOKEN` | Discord bot token. Without it the bot thread logs an error and exits; anything that needs the bot (login, superadmin checks, membership checks) returns HTTP 503. |
| `CLIENT_ID` / `CLIENT_SECRET` | Discord OAuth2 application credentials. Used by the officer login flow. |
| `REDIRECT_URI` | Must exactly match the redirect URL registered on the Discord application, e.g. `http://localhost:8000/api/auth/callback`. |
| `CLIENT_URL` | Where the API redirects the browser after a successful Discord login. In dev that's your React app, e.g. `http://localhost:5000`. |
| `SYS_ADMIN` | The Discord user ID of the superadmin. Note the mismatch: the env var is `SYS_ADMIN` but it lands on `config.SUPERADMIN_USER_ID`. |

### Feature-specific (optional — the feature just turns off)

| Variable | Feature |
|----------|---------|
| `NOTION_API_KEY`, `NOTION_DATABASE_ID` | Notion → Google Calendar sync |
| `GOOGLE_CALENDAR_ID`, `GOOGLE_USER_EMAIL` + a `google-secret.json` file at the repo root | Google Calendar API access (service account). If the file is missing, calendar features log a warning and are disabled. |
| `CLERK_SECRET_KEY`, `CLERK_AUTHORIZED_PARTIES` | Clerk-authenticated member storefront. `CLERK_AUTHORIZED_PARTIES` is a comma-separated list of allowed origins. |
| `SENTRY_DSN` | Error + log reporting to Sentry. Omit it and Sentry is skipped with a warning. |
| `LEETCODE_CHANNEL_ID`, `LEETCODE_ROLE_PING`, `LEETCODE_DAILY_TIME` | The daily LeetCode post. No channel ID = no daily post (slash commands still work). |
| `TIMEZONE` | Defaults to `America/Phoenix`. Drives the LeetCode daily schedule and new Google Calendars. |
| `FLASK_SECRET_KEY` | Flask session signing key. **Defaults to `dev-secret-key`** — must be set to a real secret in production. |
| `IS_PROD` | `true` disables the Flask debugger and reloader. Set to `true` in production. |

### Present in config but unused or legacy

`AVERY_BOT_TOKEN`, `AUTH_BOT_TOKEN`, `TNAY_API_URL`, `ONEUP_EMAIL`, `ONEUP_PASSWORD`,
`OPEN_ROUTER_CLAUDE_API_KEY`, `DISCORD_OFFICER_WEBHOOK_URL`, `DISCORD_POST_WEBHOOK_URL`,
`GEMINI_API_KEY`, and all the `DB_*` variables. The `DB_*` ones are especially misleading: the
database URL is **hardcoded** in `shared.py` as `sqlite:///./data/user.db` and the `DB_*` config
values are never read. See [Gotchas](./10-gotchas-and-known-issues.md).

## Everyday commands

```bash
make dev        # start with live logs + hot reload (this is the one you want)
make up         # start detached
make down       # stop and remove containers
make logs       # last 50 lines
make logs-follow# tail continuously
make status     # container status
make health     # is the API container healthy?
make shell      # bash shell inside the API container
make build      # rebuild both images
make clean      # down -v + prune. Destroys volumes.
```

## Before you commit

```bash
make check
```

That single target runs, in order:

1. `ruff check --fix .`  — lint, auto-fixing what it can
2. `ruff format .`       — format (line length 120, double quotes)
3. `ty check .`          — type check
4. `pytest -v`           — tests
5. `alembic upgrade head` then `alembic check` — verify migrations are applied and no model drift exists

The pre-commit hook (`.pre-commit-config.yaml`) runs exactly `make check`, and so does CI
(`.github/workflows/check.yml`). So if `make check` is green locally, CI will be green too.

To run one test file:

```bash
uv run pytest tests/test_api_endpoints.py -v
```

Note that the test suite is **integration-style**: it makes real HTTP calls against a running
server and is skipped entirely unless both `BASE_URL` and `TEST_TOKEN` env vars are set. In CI they
are not set, so the tests are collected and skipped. Do not mistake a green test run for
"the code is covered".

## Database on first boot

You do not create the database by hand. On startup:

1. `DBConnect.__init__` (`modules/utils/db.py`) creates `./data/` if it does not exist.
2. It creates the SQLite file `./data/user.db` and runs `Base.metadata.create_all()`.
3. `TokenManager` generates an RSA keypair at `./data/jwt_private.pem` and `./data/jwt_public.pem`
   if they are not already there, so JWTs survive restarts.

`./data/` is bind-mounted into the container, so all of this persists on your host.

For an existing database you should still run migrations:

```bash
make migrate     # uv run alembic upgrade head
```
