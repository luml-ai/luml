"""add_task_auto_mode

Revision ID: f1a2b3c4d5e6
Revises: e5c7b9d3f612
Create Date: 2026-05-08 00:00:00.000000

Adds the boolean ``tasks.auto_mode`` column. Defaults to false so the
agent's auto-approve / bypass-permissions flag is only appended when the
user opts in.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e5c7b9d3f612"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "auto_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "auto_mode")
