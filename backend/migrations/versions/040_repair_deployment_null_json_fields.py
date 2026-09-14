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

_JSONB_COLUMNS = (
    "dynamic_attributes_secrets",
    "env_variables_secrets",
    "env_variables",
    "satellite_parameters",
)


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


def upgrade() -> None:
    for column in _JSONB_COLUMNS:
        _abort_on_unexpected_shapes(column)
        op.execute(
            sa.text(
                f"UPDATE deployments SET {column} = '{{}}'::jsonb "  # noqa: S608
                f"WHERE jsonb_typeof({column}) = 'null'"
            )
        )
        op.create_check_constraint(
            f"deployments_{column}_is_object_check",
            "deployments",
            f"jsonb_typeof({column}) = 'object'",
        )


def downgrade() -> None:
    for column in _JSONB_COLUMNS:
        op.drop_constraint(
            f"deployments_{column}_is_object_check", "deployments", type_="check"
        )
