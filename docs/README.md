# SoDA Platform — Documentation

This folder is the knowledge-transfer pack for the SoDA Platform codebase. It is written for
someone who has never seen this repo before. Read the pages in order the first time; after that,
use it as a reference.

## What this project is, in one paragraph

The Software Developers Association (SoDA) at ASU runs its club operations on this platform. It is
a **Flask REST API** plus a **React admin web app** plus a **Discord bot**, all in one repository
and deployed as two containers. The API tracks club members, awards them "points" for showing up
to events, lets them spend those points in a merch storefront, syncs the club's Notion event
database into Google Calendar, and runs a Discord bot that posts the daily LeetCode challenge and
hosts Jeopardy games. Everything is scoped to an **organization** (a Discord server), so the same
deployment can serve multiple clubs.

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

## The 60-second orientation

```
platform/
├── main.py                 Entry point. Registers blueprints, starts the bot thread, runs Flask.
├── shared.py               Global singletons: Flask app, config, DB, token manager, Notion client.
├── modules/                All backend code. One folder per domain.
│   ├── auth/               Discord OAuth login + the auth decorators everything else uses
│   ├── bot/                Discord bot (BotFork), cogs, Jeopardy game engine, LeetCode
│   ├── calendar/           Notion → Google Calendar sync
│   ├── organizations/      Multi-tenancy: orgs, their config, their officers
│   ├── points/             Members, memberships, point transactions, leaderboards
│   ├── public/             Unauthenticated read-only endpoints
│   ├── storefront/         Products, orders, checkout paid in points
│   ├── superadmin/         Add/remove organizations, manage officer roles
│   ├── users/              Member CRUD within an organization
│   └── utils/              Config, DB connection, logging, JWT, Clerk verification
├── web/                    React admin app (Create React App)
├── alembic/                Database migrations
├── tests/                  Pytest suite (integration-style, skipped without env vars)
├── Makefile                Every command you will run
└── docker-compose.yml      Two services: api (port 8000), web (port 5000)
```

## Conventions used in these docs

- **"Org"** always means a row in the `organizations` table, which maps 1:1 to a Discord server (guild).
- **`org_prefix`** is the URL-friendly slug for an org (e.g. `soda`). Most API routes are namespaced by it.
- File references look like `modules/points/api.py:606` — path plus line number.
- Where the code and the older docs disagree, these docs describe **the code**, and the disagreement
  is called out in [Gotchas](./10-gotchas-and-known-issues.md).
