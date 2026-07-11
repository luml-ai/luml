"""Add MLModel file_name and description fields

Revision ID: 005
Revises: 004
Create Date: 2025-06-26 11:26:42.605131

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ml_models", sa.Column("file_name", sa.String(), nullable=False))
    op.add_column("ml_models", sa.Column("description", sa.String(), nullable=True))

    op.execute("UPDATE ml_models SET file_name = 'model_' || id")
    op.alter_column("ml_models", "file_name", nullable=False)


def downgrade() -> None:
    op.drop_column("ml_models", "description")
    op.drop_column("ml_models", "file_name")
