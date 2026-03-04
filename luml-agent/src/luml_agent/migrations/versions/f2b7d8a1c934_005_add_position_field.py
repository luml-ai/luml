"""005_add_position_field

Revision ID: f2b7d8a1c934
Revises: e1a4d9c7b823
Create Date: 2026-03-02 00:00:00.000000

Add nullable position column to tasks and runs tables
for drag-and-drop reordering within board columns.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b7d8a1c934"
down_revision: str | Sequence[str] | None = "e1a4d9c7b823"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("runs", sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    tasks_table = sa.Table(
        "tasks",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id", sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("branch", sa.Text(), nullable=False),
        sa.Column("worktree_path", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("tmux_session", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "tasks", copy_from=tasks_table, recreate="always",
    ) as _batch_op:
        pass

    runs_table = sa.Table(
        "runs",
        sa.MetaData(),
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "repository_id", sa.String(32),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "runs", copy_from=runs_table, recreate="always",
    ) as _batch_op:
        pass
