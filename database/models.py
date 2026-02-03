# database/models.py — модели SQLAlchemy
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Date


class Base(DeclarativeBase):
    pass


class UserStatus(str, Enum):
    PENDING_MODERATION = "pending_moderation"
    ACTIVE = "active"
    BANNED = "banned"


class UserRole(str, Enum):
    EXECUTOR = "executor"
    CUSTOMER = "customer"
    BOTH = "both"


class TenderStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=True, server_default="executor")
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), nullable=False)
    skills: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # список строк
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=UserStatus.PENDING_MODERATION.value)
    documents: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    tenders_created: Mapped[list["Tender"]] = relationship(
        "Tender", back_populates="creator", foreign_keys="Tender.created_by_user_id"
    )
    applications: Mapped[list["TenderApplication"]] = relationship(
        "TenderApplication", back_populates="user"
    )


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    budget: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=TenderStatus.DRAFT.value)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_tg_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    creator: Mapped[Optional["User"]] = relationship(
        "User", back_populates="tenders_created", foreign_keys=[created_by_user_id]
    )
    applications: Mapped[list["TenderApplication"]] = relationship(
        "TenderApplication", back_populates="tender"
    )


class TenderApplication(Base):
    __tablename__ = "tender_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="applied")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    tender: Mapped["Tender"] = relationship("Tender", back_populates="applications")
    user: Mapped["User"] = relationship("User", back_populates="applications")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False)
    application_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tender_applications.id", ondelete="CASCADE"), nullable=False
    )
    from_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
