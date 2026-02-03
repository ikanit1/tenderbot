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


def _column_exists(conn, table: str, column: str) -> bool:
    """Проверка наличия колонки (SQLite и PostgreSQL)."""
    if conn.dialect.name == "sqlite":
        r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in r)
    from sqlalchemy import inspect
    return column in [ c["name"] for c in inspect(conn).get_columns(table) ]


def upgrade() -> None:
    conn = op.get_bind()
    # users: add role (batch mode for SQLite)
    if not _column_exists(conn, "users", "role"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("role", sa.String(32), nullable=True, server_default="executor"))
        op.execute(sa.text("UPDATE users SET role = 'executor' WHERE role IS NULL"))

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


def downgrade() -> None:
    with op.batch_alter_table("tenders") as batch_op:
        batch_op.drop_constraint(
            "fk_tenders_created_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("created_by_user_id")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
