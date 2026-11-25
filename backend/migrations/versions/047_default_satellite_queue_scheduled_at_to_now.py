"""default satellite queue scheduled_at to now

Revision ID: 047
Revises: 046
Create Date: 2026-11-25 21:05:50.824654

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "047"
down_revision: str | None = "046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "satellite_queue",
        "scheduled_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        server_default=sa.text("now()"),
        existing_nullable=False,
    )
    op.execute(
        "UPDATE satellite_queue SET scheduled_at = created_at "
        "WHERE scheduled_at < created_at"
    )


def downgrade() -> None:
    op.alter_column(
        "satellite_queue",
        "scheduled_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        server_default="now()",
        existing_nullable=False,
    )
