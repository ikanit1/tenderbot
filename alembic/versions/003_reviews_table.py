"""reviews table

Revision ID: 003
Revises: 002
Create Date: 2026-02-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(conn, table: str) -> bool:
    """Проверка наличия таблицы (SQLite и PostgreSQL)."""
    if conn.dialect.name == "sqlite":
        r = conn.execute(sa.text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"))
        return r.fetchone() is not None
    from sqlalchemy import inspect
    return inspect(conn).has_table(table)


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "reviews"):
        op.create_table(
            "reviews",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tender_id", sa.Integer(), nullable=False),
            sa.Column("application_id", sa.Integer(), nullable=False),
            sa.Column("from_user_id", sa.Integer(), nullable=False),
            sa.Column("to_user_id", sa.Integer(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["application_id"], ["tender_applications.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("reviews")
