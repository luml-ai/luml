"""Model artifact to Artifact

Revision ID: 030
Revises: 029
Create Date: 2026-01-27 09:31:11.384542

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
        "model_artifacts", column_name="metrics", new_column_name="extra_values"
    )
    op.alter_column("model_artifacts", column_name="model_name", new_column_name="name")
    op.alter_column(
        "organizations",
        column_name="model_artifacts_limit",
        new_column_name="artifacts_limit",
    )

    op.alter_column(
        "deployments", column_name="model_id", new_column_name="artifact_id"
    )
    op.execute(
        "ALTER TABLE deployments "
        "RENAME CONSTRAINT deployments_model_id_fkey TO deployments_artifact_id_fkey"
    )

    op.execute(
        "ALTER INDEX ix_model_artifacts_metrics_gin "
        "RENAME TO ix_artifacts_extra_values_gin"
    )
    op.execute(
        "ALTER INDEX ix_model_artifacts_tags_gin RENAME TO ix_artifacts_tags_gin"
    )

    op.add_column(
        "model_artifacts",
        sa.Column("type", sa.String(), nullable=False, server_default="model"),
    )
    op.alter_column("model_artifacts", column_name="type", server_default=None)

    op.rename_table("model_artifacts", "artifacts")


def downgrade() -> None:
    op.rename_table("artifacts", "model_artifacts")

    op.drop_column("model_artifacts", "type")

    op.alter_column(
        "model_artifacts", column_name="extra_values", new_column_name="metrics"
    )
    op.alter_column("model_artifacts", column_name="name", new_column_name="model_name")
    op.alter_column(
        "organizations",
        column_name="artifacts_limit",
        new_column_name="model_artifacts_limit",
    )

    op.alter_column(
        "deployments", column_name="artifact_id", new_column_name="model_id"
    )
    op.execute(
        "ALTER TABLE deployments "
        "RENAME CONSTRAINT deployments_artifact_id_fkey  TO deployments_model_id_fkey"
    )

    op.execute(
        "ALTER INDEX ix_artifacts_extra_values_gin "
        "RENAME TO ix_model_artifacts_metrics_gin"
    )
    op.execute(
        "ALTER INDEX ix_artifacts_tags_gin RENAME TO ix_model_artifacts_tags_gin"
    )
