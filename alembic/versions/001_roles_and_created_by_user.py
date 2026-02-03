"""roles and created_by_user_id

Revision ID: 001
Revises:
Create Date: 2026-02-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    """Проверка наличия таблицы (SQLite и PostgreSQL)."""
    if conn.dialect.name == "sqlite":
        r = conn.execute(sa.text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"))
        return r.fetchone() is not None
    from sqlalchemy import inspect
    return inspect(conn).has_table(table)


def _column_exists(conn, table: str, column: str) -> bool:
    """Проверка наличия колонки (SQLite и PostgreSQL)."""
    if not _table_exists(conn, table):
        return False
    if conn.dialect.name == "sqlite":
        r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in r)
    from sqlalchemy import inspect
    return column in [ c["name"] for c in inspect(conn).get_columns(table) ]


def upgrade() -> None:
    conn = op.get_bind()
    
    # Если таблицы users не существует, создаем её полностью
    if not _table_exists(conn, "users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
            sa.Column("role", sa.String(32), nullable=True, server_default="executor"),
            sa.Column("full_name", sa.String(256), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=True),
            sa.Column("city", sa.String(128), nullable=False),
            sa.Column("phone", sa.String(64), nullable=False),
            sa.Column("skills", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending_moderation"),
            sa.Column("documents", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    else:
        # users: add role (batch mode for SQLite)
        if not _column_exists(conn, "users", "role"):
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(sa.Column("role", sa.String(32), nullable=True, server_default="executor"))
            op.execute(sa.text("UPDATE users SET role = 'executor' WHERE role IS NULL"))

    # Если таблицы tenders не существует, создаем её полностью
    if not _table_exists(conn, "tenders"):
        op.create_table(
            "tenders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("category", sa.String(128), nullable=False),
            sa.Column("city", sa.String(128), nullable=False),
            sa.Column("budget", sa.String(128), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("deadline", sa.DateTime(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_by_tg_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        )
    else:
        # tenders: add created_by_user_id + FK (batch mode for SQLite)
        if not _column_exists(conn, "tenders", "created_by_user_id"):
            with op.batch_alter_table("tenders") as batch_op:
                batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_tenders_created_by_user_id_users",
                    "users",
                    ["created_by_user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    
    # Создаем таблицу tender_applications, если её нет
    if not _table_exists(conn, "tender_applications"):
        op.create_table(
            "tender_applications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tender_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default="applied"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )


def downgrade() -> None:
    with op.batch_alter_table("tenders") as batch_op:
        batch_op.drop_constraint(
            "fk_tenders_created_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("created_by_user_id")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
