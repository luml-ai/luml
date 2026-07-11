"""updated org artifacts limit

Revision ID: 030
Revises: 029
Create Date: 2026-02-25 10:12:56.536726

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: str | None = "029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "organizations",
        "model_artifacts_limit",
        existing_type=sa.Integer(),
        server_default="50",
    )


def downgrade() -> None:
    op.alter_column(
        "organizations",
        "model_artifacts_limit",
        existing_type=sa.Integer(),
        server_default="200",
    )
