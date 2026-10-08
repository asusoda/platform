# Platform documentation

This folder is the knowledge-transfer pack for the Platform codebase. It is written for
someone who has never seen this repo before. Read the pages in order the first time; after that,
use it as a reference.

## What this project is, in one paragraph

Platform is shared infrastructure for student organizations. It started as the platform the
Software Developers Association (SoDA) at ASU runs its club on: a **Flask REST API**, a **React
admin web app** and a **Discord bot**, tracking members, event points, a merch store, a Notion to
Google Calendar sync, a daily LeetCode post and Jeopardy. Everything is scoped to an
**organization** (a Discord server), and each org turns modules on or off. AI Society at ASU added
modules for agents and compute: pods on RunPod that members SSH into (`compute`), per-member agent memory
(`agents`), document search with an example campus source (`knowledge`, `asu`), linked Canvas, Google and Outlook accounts
(`accounts`), app deploys (`runpod`), and an MCP server that exposes them to agents through scoped
tokens. It runs as an API, a web app, a bot process, a job worker and an MCP server.

## Read these in order

| # | Page | What you learn |
|---|------|----------------|
| 1 | [Getting Started](./01-getting-started.md) | Get it running on your machine, environment variables, day-to-day commands |
| 2 | [Architecture](./02-architecture.md) | The big picture: processes, threads, how a request flows, why files live where they do |
| 3 | [Data Model](./03-data-model.md) | Every database table, how they relate, how migrations work |
| 4 | [Authentication](./04-authentication.md) | The three (yes, three) auth systems and when each one applies |
| 5 | [Backend Modules](./05-backend-modules.md) | What each `modules/*` folder does, file by file |
| 6 | [API Reference](./06-api-reference.md) | Every HTTP endpoint, its auth requirement, and its shape |
| 7 | [Discord Bot](./07-discord-bot.md) | The bot, its cogs, slash commands, and the LeetCode daily flow |
| 8 | [Frontend](./08-frontend.md) | The React admin app: routes, pages, auth handling |
| 9 | [Deployment & Operations](./09-deployment-and-operations.md) | Docker, the Makefile, CI/CD, migrations in production, rollback |
| 10 | [Gotchas & Known Issues](./10-gotchas-and-known-issues.md) | The traps. **Read this before you change anything.** |
| 11 | [API Contract](./api-contract.md) | Every endpoint a client depends on, the contract tests that guard them, and the request log |
| 12 | [Writing a module](./writing-a-module.md) | The files a module has, where it is registered, the rules CI checks |
| 13 | [Roadmap](./roadmap.md) | What is left to build |

## Agent and compute modules

| Page | Module |
|------|--------|
| [Compute](./compute.md) | RunPod pods, SSH certificates, file manager, sessions, godfather CLI sign-in |
| [Agents](./agents.md) | Conversations, memories, profile graph, turn context and commit |
| [Knowledge](./knowledge.md) | Sources, crawls, hybrid search |
| [ASU](./asu.md) | Example campus source: ASU pages and live queries |
| [Accounts](./accounts.md) | Canvas, Google and Outlook sign-in for members |
| [Alerts](./alerts.md) | Job and hackathon listings posted to Discord webhooks |
| [Dashboard](./dashboard.md) | Officer dashboard: what is running, what failed, CI runs |
| [RunPod apps](./runpod-apps.md) | App manifests, deploys, health checks, rollback |
| [Tools and MCP](./tools-and-mcp.md) | Machine tokens, scopes, /api/tools, the MCP server |
| [RunPod deploy](./runpod-deploy.md) | Running the whole platform on one RunPod pod |

## The 60-second orientation

```
platform/
├── main.py                 API entry point. Registers blueprints, serves Flask under gunicorn.
├── bot_main.py             Discord bot process.
├── worker_main.py          Job worker (Procrastinate on Postgres).
├── mcp_main.py             MCP server for agents.
├── shared.py               Flask app, config, DB and token manager.
├── core/                   Shared code: database, config, jobs, secrets, audit, logging, RunPod client.
├── modules/                One folder per domain. Each has api.py, models.py and, where it has
│                           logic, a Flask-free service.py. modules/registry.py lists them.
│   ├── auth/               Discord login, access checks, machine tokens and scopes
│   ├── organizations/      Orgs, their config, officers, module switches
│   ├── points/, storefront/, calendar/, leetcode/, games/, users/, superadmin/, public/
│   ├── compute/            RunPod pods, SSH certificates, file manager, sessions, CLI sign-in
│   ├── agents/, knowledge/, asu/, accounts/, runpod/, mcp/
│   └── bot/                Discord bot cogs
├── web/                    React admin app
├── dashboard/              Officer dashboard (Vite + React)
├── alembic/                Database migrations
├── deploy/runpod/          Start script for a single RunPod pod
├── tests/                  Pytest suite, including contract tests for every route clients call
└── Makefile                Every command you will run
```

## Conventions used in these docs

- **"Org"** always means a row in the `organizations` table, which maps 1:1 to a Discord server (guild).
- **`org_prefix`** is the URL-friendly slug for an org (e.g. `soda`). Most API routes are namespaced by it.
- File references look like `modules/points/api.py:606` — path plus line number.
- Where the code and the older docs disagree, these docs describe **the code**, and the disagreement
  is called out in [Gotchas](./10-gotchas-and-known-issues.md).
