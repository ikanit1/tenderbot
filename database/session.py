# database/session.py — асинхронная сессия SQLAlchemy
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from config import settings
from database.models import Base

# Ленивая инициализация engine (создается только при первом использовании)
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


def get_engine() -> AsyncEngine:
    """Получить или создать async engine (ленивая инициализация)."""
    global _engine
    if _engine is None:
        # Параметры движка: для SQLite — check_same_thread=False
        _connect_args = {}
        if "sqlite" in settings.DATABASE_URL:
            _connect_args["check_same_thread"] = False
            # Для SQLite не используем pool_size и max_overflow
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                connect_args=_connect_args,
                pool_pre_ping=False,  # SQLite не поддерживает
            )
        else:
            # Для PostgreSQL и других БД используем настройки пула
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                connect_args=_connect_args,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_recycle=settings.DB_POOL_RECYCLE,
                pool_pre_ping=settings.DB_POOL_PRE_PING,
            )
    return _engine


def get_async_session_maker() -> async_sessionmaker:
    """Получить или создать async_sessionmaker (ленивая инициализация)."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


# Для обратной совместимости (используйте get_engine() и get_async_session_maker() напрямую)
# Эти переменные создаются при первом обращении
def _init_module_vars():
    """Инициализация переменных модуля для обратной совместимости."""
    global engine, async_session_maker
    if 'engine' not in globals():
        engine = get_engine()
    if 'async_session_maker' not in globals():
        async_session_maker = get_async_session_maker()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор сессии для внедрения в хендлеры (dependency)."""
    session_maker = get_async_session_maker()
    async with session_maker() as session:
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
    engine_instance = get_engine()
    async with engine_instance.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
