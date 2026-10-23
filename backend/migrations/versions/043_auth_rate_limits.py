"""Add shared authentication rate limit counters.

Revision ID: 043
Revises: 042
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limits",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("window", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", "window"),
    )
    op.create_index("ix_auth_rate_limits_window", "auth_rate_limits", ["window"])


def downgrade() -> None:
    op.drop_table("auth_rate_limits")
