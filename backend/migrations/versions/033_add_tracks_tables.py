"""Add tracks tables

Revision ID: 033
Revises: 032
Create Date: 2026-05-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("orbit_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("artifact_type", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("next_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["orbit_id"], ["orbits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("orbit_id", "name", name="uq_tracks_orbit_id_name"),
    )
    op.create_index(op.f("ix_tracks_orbit_id"), "tracks", ["orbit_id"], unique=False)

    op.create_table(
        "track_stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("track_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("track_id", "name", name="uq_track_stages_track_id_name"),
    )
    op.create_index(
        op.f("ix_track_stages_track_id"), "track_stages", ["track_id"], unique=False
    )

    op.create_table(
        "track_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("track_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=True),
        sa.Column("added_by", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stage_id"], ["track_stages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "track_id", "artifact_id", name="uq_track_entries_track_id_artifact_id"
        ),
    )
    op.create_index(
        op.f("ix_track_entries_track_id"), "track_entries", ["track_id"], unique=False
    )
    op.create_index(
        op.f("ix_track_entries_artifact_id"),
        "track_entries",
        ["artifact_id"],
        unique=False,
    )
    op.create_index(
        "ix_track_entries_track_id_stage_id_unique",
        "track_entries",
        ["track_id", "stage_id"],
        unique=True,
        postgresql_where=sa.text("stage_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("track_entries")
    op.drop_table("track_stages")
    op.drop_table("tracks")
