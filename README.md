This project provides a modular internal API and Discord bots for the Software Developers Association (SoDA) at ASU. The server side is developed using Flask, handling API requests, Discord bot interactions, and data management across all modules.

## Getting Started

### Prerequisites

- Podman and podman-compose
- Make
- uv

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/asusoda/platform.git
   cd platform
   ```
  
2. **Install dependencies & hooks:**
   ```bash
   uv sync
   uv run pre-commit install
   ```

3. **Configure environment variables:**
   ```bash
   # Copy the template environment file
   cp .env.template .env
   
   # Edit the .env file with your configuration values
   # This includes API keys, Discord bot token, etc.
   ```

4. **Start the development environment:**
   ```bash
   make dev
   ```

That's it! The application will be available at:
- API: http://localhost:8000
- Web Frontend: http://localhost:5000


## Common Commands

```bash
# Start development environment (with logs)
make dev

# Start services in background
make up

# Stop services
make down

# View logs
make logs

# Check container status
make status

# Run all checks (lint, format, typecheck, tests)
make check

### Customizing Deployment

# Open shell in API container
make shell

# Build images
make build

# Deploy to production
make deploy
```
