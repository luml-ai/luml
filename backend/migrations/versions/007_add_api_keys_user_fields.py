"""Add api-keys user fields

Revision ID: 007
Revises: 006
Create Date: 2025-07-24 13:41:39.521735

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("hashed_api_key", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "hashed_api_key")
