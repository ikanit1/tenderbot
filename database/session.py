# database/session.py — асинхронная сессия SQLAlchemy
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from config import settings
from database.models import Base

# Параметры движка: для SQLite — check_same_thread=False
_connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    _connect_args["check_same_thread"] = False
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=("sqlite" not in settings.DATABASE_URL),
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессии для внедрения в хендлеры (dependency)."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Создание таблиц при старте (альтернатива Alembic для первого запуска)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
