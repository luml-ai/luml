"""Extend the satellite contract.

Revision ID: 041
Revises: 040
Create Date: 2026-09-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "041"
down_revision: str | None = "040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _duplicate_inference_urls() -> list[str]:
    rows = op.get_bind().execute(
        sa.text(
            "SELECT inference_url FROM deployments "
            "WHERE inference_url IS NOT NULL "
            "GROUP BY inference_url HAVING count(*) > 1 "
            "ORDER BY inference_url"
        )
    )
    return [str(row.inference_url) for row in rows]


def upgrade() -> None:
    op.add_column(
        "deployments", sa.Column("provider_ref", sa.String(length=512), nullable=True)
    )
    op.add_column(
        "deployments",
        sa.Column("progress_note", sa.String(length=1000), nullable=True),
    )
    op.drop_constraint("deployments_inference_url_key", "deployments", type_="unique")
    op.add_column(
        "satellites",
        sa.Column(
            "kit_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    duplicates = _duplicate_inference_urls()
    if duplicates:
        values = ", ".join(repr(value) for value in duplicates)
        raise RuntimeError(
            f"Cannot downgrade while deployments share inference_url values: {values}"
        )

    op.create_unique_constraint(
        "deployments_inference_url_key", "deployments", ["inference_url"]
    )
    op.drop_column("satellites", "kit_info")
    op.drop_column("deployments", "progress_note")
    op.drop_column("deployments", "provider_ref")
