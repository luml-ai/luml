"""Per-user limit of organizations a user can create or join.

Revision ID: 042
Revises: 041
Create Date: 2026-09-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: str | None = "041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "organizations_limit", sa.Integer(), nullable=False, server_default="5"
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "organizations_limit")
