"""Added file_index field to MLModel

Revision ID: 004
Revises: 003
Create Date: 2025-06-23 12:58:34.606703

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ml_models",
        sa.Column(
            "file_index", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("ml_models", "file_index")
