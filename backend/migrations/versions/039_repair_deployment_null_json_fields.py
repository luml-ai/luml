"""Repair deployment JSONB columns left null by partial-update writes

The details-update handler used to send every field of the PATCH payload, so
unset fields were written back as None. SQLAlchemy stores None in a JSONB column
as the JSON value ``null``, not as SQL NULL, so the NOT NULL constraints never
rejected it -- but the read schemas type these columns as dict and reject it.

Backfill both spellings of null and add a check constraint so a future write
of a non-object fails loudly instead of corrupting the row. Any other
non-object shape is left alone and aborts the migration: those values were
never produced by this bug, so replacing them would destroy real data.

Revision ID: 039
Revises: 038
Create Date: 2026-09-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "039"
down_revision: str | None = "038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB_COLUMNS = (
    "dynamic_attributes_secrets",
    "env_variables_secrets",
    "env_variables",
    "satellite_parameters",
)


def _abort_on_unexpected_shapes(column: str) -> None:
    """Refuse to guess at values this bug could not have written."""
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT id, jsonb_typeof({column}) AS kind FROM deployments "  # noqa: S608
                f"WHERE {column} IS NOT NULL "
                f"AND jsonb_typeof({column}) NOT IN ('object', 'null') "
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
                f"WHERE {column} IS NULL OR jsonb_typeof({column}) = 'null'"
            )
        )
        op.alter_column(
            "deployments",
            column,
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            existing_server_default=sa.text("'{}'::jsonb"),
            nullable=False,
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
    # The original nulls carried no information, so there is nothing to restore.
