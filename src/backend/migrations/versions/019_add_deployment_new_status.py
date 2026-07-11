"""Add deployment new status

Revision ID: 019
Revises: 018
Create Date: 2025-10-27 08:55:57.999651

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("deployments_status_check", "deployments", type_="check")
    op.create_check_constraint(
        "deployments_status_check",
        "deployments",
        "status in ('pending','active','failed','deleted',"
        "'deletion_pending','not_responding')",
    )


def downgrade() -> None:
    op.drop_constraint("deployments_status_check", "deployments", type_="check")
    op.create_check_constraint(
        "deployments_status_check",
        "deployments",
        "status in ('pending','active','failed','deleted','deletion_pending')",
    )
