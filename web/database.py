# web/database.py — синхронная сессия БД для веб-админки (та же БД, что и бот)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings
from database.models import Base, User, Tender, TenderApplication, Review

# Синхронный URL (без asyncpg/aiosqlite)
_db_url = settings.DATABASE_URL
if "+asyncpg" in _db_url:
    _db_url = _db_url.replace("+asyncpg", "")
if "+aiosqlite" in _db_url:
    _db_url = _db_url.replace("+aiosqlite", "")

engine = create_engine(
    _db_url,
    echo=False,
    pool_pre_ping=("sqlite" not in _db_url),
    connect_args={"check_same_thread": False} if "sqlite" in _db_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
