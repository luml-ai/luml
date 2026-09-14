"""Repair deployment JSONB columns holding JSON null.

Revision ID: 040
Revises: 039
Create Date: 2026-09-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040"
down_revision: str | None = "039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _abort_on_unexpected_shapes(column: str) -> None:
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT id, jsonb_typeof({column}) AS kind FROM deployments "  # noqa: S608
                f"WHERE jsonb_typeof({column}) NOT IN ('object', 'null') "
                "LIMIT 20"
            )
        )
        .all()
    )
    if rows:
        found = ", ".join(f"{row.id} ({row.kind})" for row in rows)
        raise RuntimeError(
            f"deployments.{column} holds non-object values that this migration "
            f"will not rewrite, because doing so would discard real data: {found}. "
            "Migrate them by hand, then re-run."
        )


def _repair(column: str) -> None:
    _abort_on_unexpected_shapes(column)
    op.execute(
        sa.text(
            f"UPDATE deployments SET {column} = '{{}}'::jsonb "  # noqa: S608
            f"WHERE jsonb_typeof({column}) = 'null'"
        )
    )


def upgrade() -> None:
    _repair("dynamic_attributes_secrets")
    _repair("env_variables_secrets")
    _repair("env_variables")
    _repair("satellite_parameters")

    op.create_check_constraint(
        "deployments_dynamic_attributes_secrets_is_object_check",
        "deployments",
        "jsonb_typeof(dynamic_attributes_secrets) = 'object'",
    )
    op.create_check_constraint(
        "deployments_env_variables_secrets_is_object_check",
        "deployments",
        "jsonb_typeof(env_variables_secrets) = 'object'",
    )
    op.create_check_constraint(
        "deployments_env_variables_is_object_check",
        "deployments",
        "jsonb_typeof(env_variables) = 'object'",
    )
    op.create_check_constraint(
        "deployments_satellite_parameters_is_object_check",
        "deployments",
        "jsonb_typeof(satellite_parameters) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "deployments_satellite_parameters_is_object_check",
        "deployments",
        type_="check",
    )
    op.drop_constraint(
        "deployments_env_variables_is_object_check", "deployments", type_="check"
    )
    op.drop_constraint(
        "deployments_env_variables_secrets_is_object_check",
        "deployments",
        type_="check",
    )
    op.drop_constraint(
        "deployments_dynamic_attributes_secrets_is_object_check",
        "deployments",
        type_="check",
    )
