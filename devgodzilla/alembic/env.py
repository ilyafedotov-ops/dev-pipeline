"""
DevGodzilla Alembic Environment

Alembic migration environment for DevGodzilla database.
Supports explicit SQLite or PostgreSQL configuration.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Interpret the config file for Python logging.
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull DB settings from env and require one explicit backend.
db_url = (os.environ.get("DEVGODZILLA_DB_URL") or "").strip() or None
db_path = (os.environ.get("DEVGODZILLA_DB_PATH") or "").strip() or None
if db_url and db_path:
    raise RuntimeError(
        "Configure exactly one database backend for Alembic: set either "
        "DEVGODZILLA_DB_URL or DEVGODZILLA_DB_PATH, not both."
    )
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)
elif db_path:
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
else:
    raise RuntimeError(
        "Database is not configured for Alembic. Set exactly one of "
        "DEVGODZILLA_DB_URL or DEVGODZILLA_DB_PATH."
    )

target_metadata = None


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate
    a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
