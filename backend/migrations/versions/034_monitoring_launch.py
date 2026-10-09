"""Monitoring launch: deployment monitoring_mode + single-use launch tokens

Revision ID: 034
Revises: 033
Create Date: 2026-07-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: str | None = "033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "monitoring_mode",
            sa.String(),
            server_default="off",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "deployments_monitoring_mode_check",
        "deployments",
        "monitoring_mode in ('off','full')",
    )
    op.create_table(
        "monitoring_launch_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("jti", sa.UUID(), nullable=False),
        sa.Column("expire_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_monitoring_launch_tokens_jti"),
    )


def downgrade() -> None:
    op.drop_table("monitoring_launch_tokens")
    op.drop_constraint(
        "deployments_monitoring_mode_check", "deployments", type_="check"
    )
    op.drop_column("deployments", "monitoring_mode")
