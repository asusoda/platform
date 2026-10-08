# Bedrock

Bedrock is shared infrastructure for student organizations. Each org is a Discord server. One deployment serves many orgs, and each org turns on only the modules it uses.

It is AI Society at ASU's fork of [asusoda/platform](https://github.com/asusoda/platform), the platform the Software Developers Association (SoDA) at ASU runs its club on. Changes here are also sent upstream.

## What it does

Club operations, from SoDA's platform:

| Module | What it does |
| --- | --- |
| `points` | Members, event attendance points, leaderboards, CSV imports |
| `storefront` | Merch store paid in points, with server-checked prices |
| `calendar` | Notion events synced to Google Calendar, per-org credentials |
| `leetcode`, `games` | Daily LeetCode post and Jeopardy in Discord |
| `organizations`, `superadmin`, `users` | Orgs, officers, module switches, member records |

Added for agents and compute:

| Module | What it does |
| --- | --- |
| `compute` | GPU and CPU pods on the org's RunPod account. Members connect over SSH with 12-hour certificates through the godfather CLI. Officers get a file manager and scheduled sessions that start and stop pods around workshops. |
| `agents` | Conversations, memories and a profile graph for each member, kept for an agent such as Sparky. Retention is 180 days by default. |
| `knowledge` | Hybrid search (pgvector and full text) over documents and crawled public pages |
| `asu` | 226 public ASU pages and 16 live queries (dining, library hours, events and others), indexed into knowledge |
| `accounts` | Canvas, Google and Outlook sign-in for a member, bound to their Discord account, so agents can act for them |
| `runpod` | Deploy an org's apps to RunPod from a manifest in the app's repo, with health checks and rollback |
| `mcp` | An MCP server and `/api/tools` that expose the modules above to agents through scoped machine tokens |

Every org route checks access, every change an officer or token makes is in the audit log, and org secrets are encrypted at rest. Background work runs as jobs on Procrastinate (Postgres) or in threads (SQLite).

## Processes

| Process | Entry point | Port |
| --- | --- | --- |
| API | `main.py` (gunicorn) | 8000 |
| Web app (React) | `web/` | 5000 |
| Discord bot | `bot_main.py` | |
| Job worker | `worker_main.py` | |
| MCP server | `mcp_main.py` | 8001 |

The database is Postgres in production, or SQLite for small deployments. The schema is managed by Alembic.

## Getting started

You need Podman with podman-compose (or Docker), Make and uv.

```bash
git clone https://github.com/theaisocietyasu/bedrock.git
cd bedrock
uv sync
uv run pre-commit install
cp .env.template .env      # Discord app, bot token, secrets
make dev
```

The API is at http://localhost:8000 and the web app at http://localhost:5000. Create an org with `flask --app main org create`.

To run everything on one RunPod pod without Docker, see [docs/runpod-deploy.md](docs/runpod-deploy.md).

## Commands

```bash
make dev       # start with logs
make up        # start in the background
make down      # stop
make check     # lint, format, typecheck, tests
make shell     # shell in the API container
make deploy    # deploy to production
```

## Documentation

[docs/](docs/README.md) explains the codebase page by page, with one page per module. [docs/roadmap.md](docs/roadmap.md) is the plan and its status.

## License

BSD 3-Clause (modified for web attribution). Copyright The Software Developers Association at ASU. See [LICENSE](LICENSE).
