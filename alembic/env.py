import logging
import os
import sys
import types
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure the project root is on sys.path so module imports work.
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out ``shared`` before importing model modules.  The calendar models
# import ``shared`` transitively (calendar.models -> calendar.utils -> shared),
# which would initialise Config, the database, Discord bots, background
# threads, etc.  None of that is needed for Alembic – we only need the
# SQLAlchemy table metadata.
if "shared" not in sys.modules:
    _stub = types.ModuleType("shared")
    _stub.config = types.SimpleNamespace()  # type: ignore[attr-defined]
    _stub.logger = logging.getLogger("alembic.stub")  # type: ignore[attr-defined]
    sys.modules["shared"] = _stub

# Import the declarative Base and all model modules so that
# Base.metadata is fully populated for autogenerate support.
from modules.utils.base import Base  # noqa: E402

import modules.auth.models  # noqa: E402, F401
import modules.bot.models  # noqa: E402, F401
import modules.calendar.models  # noqa: E402, F401
import modules.organizations.models  # noqa: E402, F401
import modules.points.models  # noqa: E402, F401
import modules.storefront.models  # noqa: E402, F401

target_metadata = Base.metadata

# Allow overriding the database URL via the DATABASE_URL environment variable.
# Falls back to the value in alembic.ini (sqlalchemy.url).
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
