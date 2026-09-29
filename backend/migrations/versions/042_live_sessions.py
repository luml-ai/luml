"""Live sessions

Revision ID: 042
Revises: 041
Create Date: 2026-09-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: str | None = "041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "live_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("orbit_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("relay_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_live_sessions_orbit_id"), "live_sessions", ["orbit_id"], unique=False
    )
    op.create_index(
        op.f("ix_live_sessions_user_id"), "live_sessions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_live_sessions_user_id"), table_name="live_sessions")
    op.drop_index(op.f("ix_live_sessions_orbit_id"), table_name="live_sessions")
    op.drop_table("live_sessions")
