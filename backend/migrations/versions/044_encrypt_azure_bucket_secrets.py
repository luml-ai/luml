"""Encrypt Azure bucket connection strings.

Revision ID: 044
Revises: 043
Create Date: 2026-10-08 00:00:00.000000

"""

from collections.abc import Callable, Sequence

import sqlalchemy as sa
from alembic import op
from luml.infra.encryption import decrypt, encrypt

revision: str = "044"
down_revision: str | None = "043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rewrite_azure_endpoints(transform: Callable[[str], str]) -> None:
    connection = op.get_bind()
    secrets = connection.execute(
        sa.text("SELECT id, endpoint FROM bucket_secrets WHERE type = 'azure'")
    ).all()
    for secret in secrets:
        connection.execute(
            sa.text("UPDATE bucket_secrets SET endpoint = :endpoint WHERE id = :id"),
            {"id": secret.id, "endpoint": transform(secret.endpoint)},
        )


def upgrade() -> None:
    _rewrite_azure_endpoints(encrypt)


def downgrade() -> None:
    _rewrite_azure_endpoints(decrypt)
