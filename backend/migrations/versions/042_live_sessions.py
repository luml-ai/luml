"""Live sessions and relays

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
        "relays",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("base_domain", sa.String(), nullable=False),
        sa.Column("agent_url", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="enabled", nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("previous_token_hash", sa.String(), nullable=True),
        sa.Column(
            "previous_token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_agents", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("base_domain"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_relays_organization_id"), "relays", ["organization_id"], unique=False
    )
    op.create_index(
        op.f("ix_relays_previous_token_hash"),
        "relays",
        ["previous_token_hash"],
        unique=False,
    )
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
    op.drop_index(op.f("ix_relays_previous_token_hash"), table_name="relays")
    op.drop_index(op.f("ix_relays_organization_id"), table_name="relays")
    op.drop_table("relays")
