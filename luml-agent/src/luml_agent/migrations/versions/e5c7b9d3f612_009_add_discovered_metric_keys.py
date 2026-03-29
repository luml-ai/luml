"""009_add_discovered_metric_keys

Revision ID: e5c7b9d3f612
Revises: d4f6a8c2e501
Create Date: 2026-03-29 00:00:00.000000

Add discovered_metric_keys_json column to runs table to store
metric key names discovered from the first successful run node.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5c7b9d3f612"
down_revision: str | Sequence[str] | None = "d4f6a8c2e501"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "discovered_metric_keys_json", sa.Text(),
            nullable=False, server_default="[]",
        ),
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
        sa.Column(
            "best_node_id", sa.String(32),
            sa.ForeignKey("run_nodes.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    with op.batch_alter_table(
        "runs", copy_from=runs_table, recreate="always",
    ) as _batch_op:
        pass
