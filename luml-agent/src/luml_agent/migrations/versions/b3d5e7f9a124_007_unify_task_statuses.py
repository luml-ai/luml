"""007_unify_task_statuses

Revision ID: b3d5e7f9a124
Revises: a1c3e5f7b902
Create Date: 2026-03-02 00:00:00.000000

Rename task statuses: done→succeeded, error→failed.
Aligns task and run status vocabulary.
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "b3d5e7f9a124"
down_revision: str | Sequence[str] | None = "a1c3e5f7b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE tasks SET status = 'succeeded' WHERE status = 'done'"))
    conn.execute(text("UPDATE tasks SET status = 'failed' WHERE status = 'error'"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("UPDATE tasks SET status = 'done' WHERE status = 'succeeded'"))
    conn.execute(text("UPDATE tasks SET status = 'error' WHERE status = 'failed'"))
