"""008_add_best_node_id

Revision ID: d4f6a8c2e501
Revises: b3d5e7f9a124
Create Date: 2026-03-04 00:00:00.000000

Add nullable best_node_id column to runs table to track
the best-performing implement node after run completion.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6a8c2e501"
down_revision: str | Sequence[str] | None = "b3d5e7f9a124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("best_node_id", sa.String(32), nullable=True),
    )


def downgrade() -> None:
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
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("base_branch", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "runs", copy_from=runs_table, recreate="always",
    ) as _batch_op:
        pass
