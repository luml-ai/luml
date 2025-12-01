"""Added created by to model_artifacts

Revision ID: 025
Revises: 023
Create Date: 2025-11-17 20:26:41.201849

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "deployments",
        "schemas",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        existing_server_default=sa.text("'{}'::jsonb"),
    )

    op.add_column(
        "model_artifacts",
        sa.Column(
            "created_by_user", sa.String(), nullable=False, server_default="unknown"
        ),
    )

    op.alter_column("model_artifacts", "created_by_user", server_default=None)


def downgrade() -> None:
    op.drop_column("model_artifacts", "created_by_user")
    op.alter_column(
        "deployments",
        "schemas",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        existing_server_default=sa.text("'{}'::jsonb"),
    )
