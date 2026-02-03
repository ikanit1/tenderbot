# alembic/env.py — окружение для миграций (синхронный драйвер)
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Импорт конфига и моделей
from config import settings
from database.models import Base

# URL для Alembic: синхронный (postgresql://) для миграций
config = context.config
database_url = settings.DATABASE_URL
if "+asyncpg" in database_url:
    database_url = database_url.replace("+asyncpg", "")
if "+aiosqlite" in database_url:
    database_url = database_url.replace("+aiosqlite", "")
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме (только генерация SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    # render_as_batch=True: SQLite batch mode (create new table, copy data, drop old).
    # Requires alembic>0.7.0. See: https://alembic.sqlalchemy.org/en/latest/batch.html
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # render_as_batch=True: SQLite batch ops. FK drop nuance: see batch.html#dropping-unnamed-or-named-foreign-key-constraints
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме (подключение к БД)."""
    connectable = context.config.attributes.get("connection", None)
    if connectable is None:
        from sqlalchemy import create_engine
        connectable = create_engine(
            config.get_main_option("sqlalchemy.url"),
            poolclass=pool.NullPool,
        )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
