"""Repair deployment JSONB columns left null by partial-update writes

The details-update handler used to send every field of the PATCH payload, so
unset fields were written back as None. SQLAlchemy stores None in a JSONB column
as the JSON value ``null``, not as SQL NULL, so the NOT NULL constraints never
rejected it -- but the read schemas type these columns as dict and reject it.

Backfill both spellings of the empty value and add a check constraint so a
future write of a non-object fails loudly instead of corrupting the row.

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


def upgrade() -> None:
    for column in _JSONB_COLUMNS:
        op.execute(
            sa.text(
                f"UPDATE deployments SET {column} = '{{}}'::jsonb "  # noqa: S608
                f"WHERE {column} IS NULL OR jsonb_typeof({column}) <> 'object'"
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
