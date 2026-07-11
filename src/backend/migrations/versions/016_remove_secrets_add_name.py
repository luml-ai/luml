"""016_remove_secrets_add_name

Revision ID: 016
Revises: 015
Create Date: 2025-09-15 14:04:02.171117

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from alembic.ddl import postgresql

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("deployments", "secrets")
    op.add_column("deployments", sa.Column("name", sa.String(), nullable=True))
    op.drop_constraint("deployments_status_check", "deployments", type_="check")
    op.create_check_constraint(
        "deployments_status_check",
        "deployments",
        "status in ('pending','active','failed','deleted','deletion_pending')",
    )


def downgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column(
            "secrets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.drop_column("deployments", "name")
    op.drop_constraint("deployments_status_check", "deployments", type_="check")
    op.create_check_constraint(
        "deployments_status_check",
        "deployments",
        "status in ('pending','active','failed','deleted')",
    )
