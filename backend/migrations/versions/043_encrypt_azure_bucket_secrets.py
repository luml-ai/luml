"""Encrypt Azure bucket connection strings.

Revision ID: 043
Revises: 042
Create Date: 2026-10-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from luml.infra.encryption import decrypt, encrypt
from luml.schemas.bucket_secrets import azure_public_endpoint

revision: str = "043"
down_revision: str | None = "042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    secrets = connection.execute(
        sa.text(
            "SELECT id, endpoint, bucket_name, organization_id "
            "FROM bucket_secrets WHERE type = 'azure'"
        )
    ).all()
    identities = set()
    for secret in secrets:
        identity = (
            azure_public_endpoint(secret.endpoint),
            secret.bucket_name,
            secret.organization_id,
        )
        if identity in identities:
            raise RuntimeError(
                "Duplicate Azure buckets must be resolved before migration"
            )
        identities.add(identity)

    op.add_column(
        "bucket_secrets", sa.Column("connection_string", sa.String(), nullable=True)
    )
    for secret in secrets:
        connection.execute(
            sa.text(
                "UPDATE bucket_secrets SET endpoint = :endpoint, "
                "connection_string = :connection_string WHERE id = :id"
            ),
            {
                "id": secret.id,
                "endpoint": azure_public_endpoint(secret.endpoint),
                "connection_string": encrypt(secret.endpoint),
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    secrets = connection.execute(
        sa.text("SELECT id, connection_string FROM bucket_secrets WHERE type = 'azure'")
    ).all()
    for secret in secrets:
        connection.execute(
            sa.text("UPDATE bucket_secrets SET endpoint = :endpoint WHERE id = :id"),
            {"id": secret.id, "endpoint": decrypt(secret.connection_string)},
        )
    op.drop_column("bucket_secrets", "connection_string")
