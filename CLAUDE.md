# {CLAUDE,AGENTS}.md

This file provides guidance to AI agents when working with code in this repository.

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
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_filename.py -v

# Install dependencies for testing
uv sync
```

### Code Quality
```bash
# Install pre-commit hooks
uv run pre-commit install

# Run linting and formatting
uv run ruff check --fix .
uv run ruff format .

# Run type checking
uv run ty check .

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
- **Discord Bots**: Two separate bot instances (summarizer and auth) running in dedicated threads
- **Multi-Organization Support**: Organization-scoped data and configurations
- **Containerized Deployment**: Docker/Podman with docker-compose for orchestration

### Key Components

#### Module System
All core functionality is organized in `/modules/` with consistent structure:
- `api.py` - REST endpoints and route handlers
- `models.py` - SQLAlchemy database models  
- `README.md` - Module documentation

Active modules: auth, bot, calendar, merch, organizations, points, public, superadmin, users, utils

#### Database Architecture
- SQLite database (`./data/user.db`) with SQLAlchemy ORM
- Base model class in `modules/utils/base.py`
- Centralized connection management via `DBConnect` class
- Automatic table creation on startup

#### Discord Integration
- **Auth Bot**: BotFork instance with HelperCog and GameCog for server management
- Bot runs in separate asyncio event loop in daemon thread
- Bot token managed via environment variable (`BOT_TOKEN`)

#### Background Services
- **Calendar Sync Service**: Syncs Notion data to Google Calendar (runs every 120 minutes)
- **Token Cleanup**: Automatic cleanup of expired refresh tokens (runs hourly)
- **Multi-org Calendar Service**: Handles calendar operations across organizations

### Configuration Management
- Environment variables via `.env` file (not tracked in git)
- `Config` class in `modules/utils/config.py` centralizes configuration
- Organization-specific configs stored in database
- Sentry integration for error monitoring

### Frontend Integration  
- React app in `/web/` directory with separate package.json
- Built files served from `/web/build/` 
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
- Runs ruff (lint + format) and ty automatically on commits
- Install with `uv run pre-commit install`
- All checks also run in CI on every push/PR
