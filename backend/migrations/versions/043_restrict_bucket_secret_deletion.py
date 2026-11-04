"""Restrict deletion of bucket secrets used by orbits.

Revision ID: 043
Revises: 042
Create Date: 2026-10-22 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("orbits_bucket_secret_id_fkey", "orbits", type_="foreignkey")
    op.create_foreign_key(
        "orbits_bucket_secret_id_fkey",
        "orbits",
        "bucket_secrets",
        ["bucket_secret_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("orbits_bucket_secret_id_fkey", "orbits", type_="foreignkey")
    op.create_foreign_key(
        "orbits_bucket_secret_id_fkey",
        "orbits",
        "bucket_secrets",
        ["bucket_secret_id"],
        ["id"],
        ondelete="CASCADE",
    )
