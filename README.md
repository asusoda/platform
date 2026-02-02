This project provides a modular internal API and Discord bots for the Software Developers Association (SoDA) at ASU. The server side is developed using Flask, handling API requests, Discord bot interactions, and data management across all modules.

## Directory

- [Main Documentation](#) - This README file
- [Module Documentation](./modules/README.md) - Detailed information on available modules
  - [Auth Module](./modules/auth/README.md)
  - [Bot Module](./modules/bot/README.md)
  - [Calendar Module](./modules/calendar/README.md)
  - [Organizations Module](./modules/organizations/README.md)
  - [Points Module](./modules/points/README.md)
  - [Storefront Module](./modules/storefront/README.md)
  - [Users Module](./modules/users/README.md)

## Getting Started

### Prerequisites

- Podman and podman-compose
- Make

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/asusoda/soda-internal-api.git
   cd soda-internal-api
   ```

2. **Configure environment variables:**
   ```bash
   # Copy the template environment file
   cp .env.template .env
   
   # Edit the .env file with your configuration values
   # This includes API keys, Discord bot token, etc.
   ```

3. **Start the development environment:**
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


### Customizing Deployment

# Open shell in API container
make shell

# Build images
make build

# Deploy to production
make deploy
```

## Code Quality & Linting

This project uses automated linting and type checking to maintain code quality:

### Tools

- **ruff**: Fast Python linter and formatter
- **ty**: Type checker written in Rust
- **mypy**: Additional type checking
- **bandit**: Security vulnerability scanner

### Running Locally

```bash
# Install dependencies (including dev tools)
uv sync

# Run ruff linting
uv run ruff check .

# Auto-fix ruff issues
uv run ruff check --fix .

# Check code formatting
uv run ruff format --check .

# Format code
uv run ruff format .

# Run ty type checking
uv run ty check .

# Run all checks (same as CI)
uv run ruff check . && uv run ruff format --check . && uv run ty check .
```

### Git Hooks

Pre-commit and pre-push hooks are configured via **husky** to automatically run linting and type checking before commits and pushes.

**Setup (after cloning):**
```bash
# Install npm dependencies (including husky)
npm install

# Hooks are automatically installed via the "prepare" script
```

The hooks will:
1. Run ruff linting
2. Check code formatting
3. Run ty type checking

If any checks fail, the commit/push will be blocked until issues are fixed.

### CI/CD

All linting and type checking runs automatically on:
- Every push to any branch
- Every pull request

The CI workflow runs:
- Ruff linting and formatting checks
- Ty type checking
- Mypy type checking
- Bandit security checks


## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Contact

For any questions or feedback, please reach out to asu@thesoda.io
