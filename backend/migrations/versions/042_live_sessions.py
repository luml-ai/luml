"""Live sessions, relays, tunnel tokens, flows and organization session limits

Revision ID: 042
Revises: 041
Create Date: 2026-09-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

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
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
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
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False),
        sa.Column("relay_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_viewer_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relay_id"], ["relays.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_live_sessions_orbit_id"), "live_sessions", ["orbit_id"], unique=False
    )
    op.create_index(
        op.f("ix_live_sessions_user_id"), "live_sessions", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_live_sessions_relay_id"), "live_sessions", ["relay_id"], unique=False
    )
    op.create_table(
        "live_session_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("destination", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"], ["live_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_live_session_tokens_session_id"),
        "live_session_tokens",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_live_session_tokens_user_id"),
        "live_session_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_live_session_tokens_expires_at"),
        "live_session_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "flows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("orbit_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["live_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "orbit_id", "user_id", "name", name="flows_orbit_id_user_id_name_key"
        ),
    )
    op.create_index(op.f("ix_flows_user_id"), "flows", ["user_id"], unique=False)
    op.create_index(op.f("ix_flows_session_id"), "flows", ["session_id"], unique=False)
    op.add_column("orbits", sa.Column("relay_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "orbits_relay_id_fkey",
        "orbits",
        "relays",
        ["relay_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "organizations",
        sa.Column(
            "managed_relay_sessions_limit",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "own_relay_sessions_limit",
            sa.Integer(),
            server_default="5",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "own_relay_sessions_limit")
    op.drop_column("organizations", "managed_relay_sessions_limit")
    op.drop_constraint("orbits_relay_id_fkey", "orbits", type_="foreignkey")
    op.drop_column("orbits", "relay_id")
    op.drop_index(op.f("ix_flows_session_id"), table_name="flows")
    op.drop_index(op.f("ix_flows_user_id"), table_name="flows")
    op.drop_table("flows")
    op.drop_index(
        op.f("ix_live_session_tokens_expires_at"), table_name="live_session_tokens"
    )
    op.drop_index(
        op.f("ix_live_session_tokens_user_id"), table_name="live_session_tokens"
    )
    op.drop_index(
        op.f("ix_live_session_tokens_session_id"), table_name="live_session_tokens"
    )
    op.drop_table("live_session_tokens")
    op.drop_index(op.f("ix_live_sessions_relay_id"), table_name="live_sessions")
    op.drop_index(op.f("ix_live_sessions_user_id"), table_name="live_sessions")
    op.drop_index(op.f("ix_live_sessions_orbit_id"), table_name="live_sessions")
    op.drop_table("live_sessions")
    op.drop_index(op.f("ix_relays_previous_token_hash"), table_name="relays")
    op.drop_index(op.f("ix_relays_organization_id"), table_name="relays")
    op.drop_table("relays")
