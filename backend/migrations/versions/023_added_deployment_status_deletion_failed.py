"""added deployment status deletion failed

Revision ID: 023
Revises: 022
Create Date: 2025-11-05 17:22:20.521641

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "023"
down_revision: str | None = "022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM deployments WHERE status = 'deleted'"))

    op.drop_constraint("deployments_status_check", "deployments", type_="check")
    op.create_check_constraint(
        "deployments_status_check",
        "deployments",
        "status in ('pending','active','failed','deletion_failed',"
        "'deletion_pending','not_responding')",
    )


def downgrade() -> None:
    op.drop_constraint("deployments_status_check", "deployments", type_="check")
    op.create_check_constraint(
        "deployments_status_check",
        "deployments",
        "status in ('pending','active','failed','deletion_failed','deletion_pending')",
    )
