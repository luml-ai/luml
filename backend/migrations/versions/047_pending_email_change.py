"""pending email change

Revision ID: 047
Revises: 046
Create Date: 2026-11-25 13:20:08.129526

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "047"
down_revision: str | None = "046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("pending_email_change_id", sa.UUID(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "pending_email_change_id")
