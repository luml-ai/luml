"""drop old id columns

Revision ID: 046
Revises: 045
Create Date: 2026-11-25 17:52:53.683927

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: str | None = "045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("artifacts", "old_id")
    op.drop_column("bucket_secrets", "old_id")
    op.drop_column("collections", "old_id")
    op.drop_column("deployments", "old_id")
    op.drop_column("orbit_members", "old_id")
    op.drop_column("orbit_secrets", "old_id")
    op.drop_column("orbits", "old_id")
    op.drop_column("organization_invites", "old_id")
    op.drop_column("organization_members", "old_id")
    op.drop_column("organizations", "old_id")
    op.drop_column("satellite_queue", "old_id")
    op.drop_column("satellites", "old_id")
    op.drop_column("stats_emails", "old_id")
    op.drop_column("token_black_list", "old_id")
    op.drop_column("users", "old_id")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "token_black_list",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "stats_emails",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "satellites",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "satellite_queue",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "organization_members",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "organization_invites",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "orbits",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "orbit_secrets",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "orbit_members",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "collections",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "bucket_secrets",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "artifacts",
        sa.Column("old_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
