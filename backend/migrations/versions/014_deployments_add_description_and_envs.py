"""Add deployment description and env fields

Revision ID: 014
Revises: 013
Create Date: 2025-09-13 08:51:22.612526

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "deployments",
        sa.Column("description", sa.String(), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column(
            "dynamic_attributes_secrets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "deployments",
        sa.Column(
            "env_variables_secrets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "deployments",
        sa.Column(
            "env_variables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("deployments", "env_variables")
    op.drop_column("deployments", "env_variables_secrets")
    op.drop_column("deployments", "dynamic_attributes_secrets")
    op.drop_column("deployments", "description")
