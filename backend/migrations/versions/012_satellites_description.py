"""Satellites description

Revision ID: 012
Revises: 011
Create Date: 2025-09-03 14:20:10.956992

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("satellites", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("satellites", "description")
