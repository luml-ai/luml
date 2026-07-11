"""Add model_name field to MLModel

Revision ID: 006
Revises: 005
Create Date: 2025-07-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ml_models", sa.Column("model_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("ml_models", "model_name")
