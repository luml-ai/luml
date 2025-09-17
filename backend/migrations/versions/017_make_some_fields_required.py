"""017_make_some_fields_required

Revision ID: 017
Revises: 016
Create Date: 2025-09-17 15:41:35.606782

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("deployments", "name", existing_type=sa.VARCHAR(), nullable=False)
    op.alter_column(
        "model_artifacts", "model_name", existing_type=sa.VARCHAR(), nullable=False
    )
    op.alter_column("satellites", "name", existing_type=sa.VARCHAR(), nullable=False)


def downgrade() -> None:
    op.alter_column("satellites", "name", existing_type=sa.VARCHAR(), nullable=True)
    op.alter_column(
        "model_artifacts", "model_name", existing_type=sa.VARCHAR(), nullable=True
    )
    op.alter_column("deployments", "name", existing_type=sa.VARCHAR(), nullable=True)
