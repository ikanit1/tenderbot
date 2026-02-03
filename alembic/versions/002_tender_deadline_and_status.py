"""tender deadline and status values

Revision ID: 002
Revises: 001
Create Date: 2026-02-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    if conn.dialect.name == "sqlite":
        r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in r)
    from sqlalchemy import inspect
    return column in [c["name"] for c in inspect(conn).get_columns(table)]


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "tenders", "deadline"):
        with op.batch_alter_table("tenders") as batch_op:
            batch_op.add_column(sa.Column("deadline", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenders") as batch_op:
        batch_op.drop_column("deadline")
