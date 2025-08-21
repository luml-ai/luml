"""Organization limits

Revision ID: 009
Revises: 008
Create Date: 2025-08-11 16:21:46.677447

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("members_limit", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("orbits_limit", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("organizations", "orbits_limit")
    op.drop_column("organizations", "members_limit")
