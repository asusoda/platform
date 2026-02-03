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

## Code Quality

This project uses ruff for linting/formatting and ty for type checking. Git hooks via pre-commit run these automatically.

**Setup:**
```bash
uv sync                    # Install dependencies
uv run pre-commit install  # Install git hooks
```

**Manual runs:**
```bash
uv run ruff check --fix .  # Lint and auto-fix
uv run ruff format .       # Format code
uv run ty check .          # Type check
```


## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Contact

For any questions or feedback, please reach out to asu@thesoda.io
