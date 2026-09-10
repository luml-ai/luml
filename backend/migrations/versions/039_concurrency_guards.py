"""Concurrency guards: unique rules and a strict stage foreign key

Revision ID: 039
Revises: 038
Create Date: 2026-09-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stage_foreign_key_name() -> str:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys("track_entries"):
        if foreign_key["constrained_columns"] == ["stage_id"]:
            return str(foreign_key["name"])
    raise RuntimeError("track_entries.stage_id foreign key not found")


def upgrade() -> None:
    # Refresh-token blacklist: one row per token, so revoking is atomic.
    op.execute(
        "DELETE FROM token_black_list a USING token_black_list b "
        "WHERE a.token = b.token AND ("
        "a.expire_at < b.expire_at "
        "OR (a.expire_at = b.expire_at AND a.id > b.id))"
    )
    op.create_unique_constraint(
        "uq_token_black_list_token", "token_black_list", ["token"]
    )

    # Invites: one pending invite per organization and email (keep the newest).
    op.execute(
        "DELETE FROM organization_invites a USING organization_invites b "
        "WHERE a.organization_id = b.organization_id "
        "AND a.email = b.email AND a.id < b.id"
    )
    op.create_unique_constraint(
        "uq_organization_invites_organization_id_email",
        "organization_invites",
        ["organization_id", "email"],
    )

    # Track stages: at most one entry per stage (keep the highest version).
    op.execute(
        "UPDATE track_entries e SET stage_id = NULL "
        "WHERE e.stage_id IS NOT NULL AND EXISTS ("
        "SELECT 1 FROM track_entries o WHERE o.track_id = e.track_id "
        "AND o.stage_id = e.stage_id AND o.version > e.version)"
    )
    op.create_index(
        "uq_track_entries_track_id_stage_id",
        "track_entries",
        ["track_id", "stage_id"],
        unique=True,
        postgresql_where=sa.text("stage_id IS NOT NULL"),
    )

    # Deleting a stage must not clear entries silently.
    op.drop_constraint(_stage_foreign_key_name(), "track_entries", type_="foreignkey")
    op.create_foreign_key(
        "fk_track_entries_stage_id_track_stages",
        "track_entries",
        "track_stages",
        ["stage_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_track_entries_stage_id_track_stages", "track_entries", type_="foreignkey"
    )
    op.create_foreign_key(
        "track_entries_stage_id_fkey",
        "track_entries",
        "track_stages",
        ["stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("uq_track_entries_track_id_stage_id", table_name="track_entries")
    op.drop_constraint(
        "uq_organization_invites_organization_id_email",
        "organization_invites",
        type_="unique",
    )
    op.drop_constraint("uq_token_black_list_token", "token_black_list", type_="unique")
