"""Add deployment monitoring URL

Revision ID: 037
Revises: 036
Create Date: 2026-08-27 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column("monitoring_url", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deployments", "monitoring_url")
