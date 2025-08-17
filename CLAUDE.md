# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
poetry run pytest -v

# Run specific test file
poetry run pytest tests/test_filename.py -v

# Install dependencies for testing
poetry install --no-interaction --no-root
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

Active modules: auth, bot, calendar, merch, ocp, organizations, points, public, summarizer, superadmin, users, utils

#### Database Architecture
- SQLite database (`./data/user.db`) with SQLAlchemy ORM
- Base model class in `modules/utils/base.py`
- Centralized connection management via `DBConnect` class
- Automatic table creation on startup

#### Discord Integration
- **Auth Bot**: BotFork instance with HelperCog and GameCog for server management
- **Summarizer Bot**: Standard discord.Bot for content summarization features
- Both run in separate asyncio event loops in daemon threads
- Bot tokens managed via environment variables (`BOT_TOKEN`, `AVERY_BOT_TOKEN`)

#### Background Services
- **Unified Sync Service**: Syncs Notion data to Google Calendar and OCP database (runs every 60 minutes)
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

## Important Notes

### Environment Setup
- Copy `.env.template` to `.env` and configure before running
- Requires Discord bot tokens, Google API credentials, Notion API key
- Database file created automatically in `./data/` directory

### Testing Environment
- Set `TESTING=true` environment variable for test runs
- Poetry manages Python dependencies and virtual environment
- GitHub Actions runs tests automatically on push/PR

### Container Architecture
- API container exposes port 8000
- Web container exposes port 5000  
- Shared data volume for persistence
- Health checks configured for both services
- Buildkit enabled for optimized builds