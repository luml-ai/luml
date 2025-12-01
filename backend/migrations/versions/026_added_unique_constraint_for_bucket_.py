"""Added unique constraint for bucket secret

Revision ID: 026
Revises: 023
Create Date: 2025-11-10 19:39:41.941519

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "026"
down_revision: str | None = "025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE bucket_secrets
        SET bucket_name = bucket_name || ' DUPLICATE [' || id::text || ']'
        WHERE id IN (
            SELECT a.id
            FROM bucket_secrets a
            INNER JOIN bucket_secrets b ON
                a.endpoint = b.endpoint AND
                a.bucket_name = b.bucket_name AND
                a.organization_id = b.organization_id AND
                a.id < b.id
        )
    """)

    op.create_unique_constraint(
        "uq_bucket_endpoint",
        "bucket_secrets",
        ["endpoint", "bucket_name", "organization_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_bucket_endpoint", "bucket_secrets", type_="unique")
