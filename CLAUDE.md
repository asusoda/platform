# {CLAUDE,AGENTS}.md

This file provides guidance to AI agents when working with code in this repository.

## Skills

Procedures for agents are in `.agents/skills/` (linked from `.claude/skills/`), listed in `.agents/README.md`. Use `check` before every commit, `new-module` when adding a module, `migration` for model changes, `api-contract` when touching a route thesoda.io or `web/` calls, and `pr-ready` before opening a PR.

## Development Commands

### Primary Development Workflow
```bash
# Start development environment (with live logs)
make dev

# Start services in background 
make up

# Stop services
make down

# View logs
make logs

# Check container status
make status

# Open shell in API container
make shell

# Build images
make build
```

### Testing
```bash
# Run all checks (lint, format, typecheck, tests)
make check

# Run specific test file
uv run pytest tests/test_filename.py -v

# Install dependencies for testing
uv sync
```

### Code Quality
```bash
# Install pre-commit hooks
uv run pre-commit install

# Run all checks (lint, format, typecheck, tests)
make check

# Run all pre-commit hooks manually
uv run pre-commit run --all-files
```

### Deployment
```bash
# Deploy to production
make deploy

# Health check
make health-check

# Rollback to previous version
make rollback
```

## Architecture Overview

### Core Structure
- **Flask API Backend**: Main application in `main.py` with modular blueprint architecture
- **React Frontend**: Located in `web/` directory with separate build process
- **Discord Bot**: One bot, run as its own process by `bot_main.py`
- **Job worker and MCP server**: `worker_main.py` (Procrastinate on Postgres) and `mcp_main.py`
- **Multi-Organization Support**: Organization-scoped data and configurations
- **Containerized Deployment**: Docker/Podman with docker-compose for orchestration

### Key Components

#### Module System
All core functionality is organized in `/modules/`, one folder per feature. A module has only the files it needs:
- `README.md` - what it does, its files, routes, jobs, tools and tables
- `service.py` - logic; takes a DB session, never imports Flask, raises a `core.errors.ServiceError` subclass
- `api.py` - Flask blueprint that calls `service.py`; officer and machine-token routes use `officer_route` and `machine_route` from `modules/auth/routes.py`
- `models.py` - SQLAlchemy models
- `jobs.py`, `tools.py` - background jobs (`@job`) and agent tools (`@tool`)

Blueprints are mounted in `modules/registry.py`; model, job and tool modules are listed in `modules/manifest.py`. `docs/writing-a-module.md` lists every place a new module is registered.

Active modules: accounts, agents, alerts, asu, auth, bot, calendar, compute, dashboard, games, knowledge, leetcode, mcp, organizations, points, public, runpod, storefront, superadmin, users. Shared code (database, config, logging, HTTP hooks, Discord and RunPod clients) is in `core/`.

#### Database Architecture
- SQLite database (`./data/user.db`) with SQLAlchemy ORM
- Base model class in `core/db/base.py`
- Centralized connection management via `DBConnect` class
- Schema managed by Alembic migrations (`alembic upgrade head`); no table creation at startup

#### Discord Integration
- BotFork instance in `modules/bot/`, loading cogs from `modules/games` and `modules/leetcode`
- Runs in its own process (`bot_main.py`); the API reaches Discord over REST (`core/integrations/discord.py`)
- Bot token managed via environment variable (`BOT_TOKEN`)

#### Background Jobs
- Declared per module in `jobs.py` with `@job` from `core/jobs.py`, listed in `modules/manifest.py`
- Postgres: Procrastinate queue, run by `worker_main.py`. SQLite: run in threads of the API process
- Hourly refresh-token cleanup, CSV point imports, calendar sync when `CALENDAR_SYNC_CRON` is set

### Configuration Management
- Environment variables via `.env` file (not tracked in git)
- `Config` class in `core/config.py` centralizes configuration
- Organization-specific configs stored in database
- Sentry integration for error monitoring

### Frontend Integration  
- React app in `/web/` directory with separate package.json
- Built files served from `/web/build/` 
- Officer dashboard in `/dashboard/` (Vite, React, Tailwind), see `docs/dashboard.md`
- CORS configured for local development and production domains
- API communication via axios with organization headers

## Development Best Practices

### Environment Setup
- Copy `.env.template` to `.env` and configure before running
- Requires Discord bot token, Google API credentials, Notion API key
- Database file created automatically in `./data/` directory

### Testing Environment
- uv manages Python dependencies and virtual environment
- GitHub Actions runs tests automatically on push/PR

### Container Architecture
- API container exposes port 8000
- Web container exposes port 5000  
- Shared data volume for persistence
- Health checks configured for both services
- Buildkit enabled for optimized builds

### Logging
- Stay away from vanilla `print()` statements. There's a shared logging module. Use that instead.

## Code Quality Tools

### Linting & Formatting
- **ruff**: Fast Python linter and formatter (configured in pyproject.toml)
  - Line length: 120
  - Auto-formats code and checks style
  
### Type Checking
- **ty**: Rust-based type checker for Python

### Pre-commit Hooks
- Configured via `.pre-commit-config.yaml`
- Runs `make check` (lint, format, typecheck, tests) automatically on commits
- Install with `uv run pre-commit install`
- All checks also run in CI on every push/PR
