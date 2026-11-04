from uuid import uuid7

from luml.infra.encryption import decrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.alembic import run_alembic
from tests.support.bucket_secrets import CONNECTION_STRING
from tests.support.seeds import OrganizationFixtureData


async def test_migration_encrypts_legacy_azure_secrets_and_preserves_s3(
    engine: AsyncEngine, seeded_organization: OrganizationFixtureData
) -> None:
    await run_alembic(engine, "downgrade", "043")
    secret_id = uuid7()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO bucket_secrets "
                "(id, organization_id, type, endpoint, bucket_name, created_at) "
                "VALUES (:id, :organization_id, 'azure', :endpoint, 'legacy', now())"
            ),
            {
                "id": secret_id,
                "organization_id": seeded_organization.organization.id,
                "endpoint": CONNECTION_STRING,
            },
        )
    await run_alembic(engine, "upgrade", "head")

    async with engine.connect() as connection:
        azure_endpoint = await connection.scalar(
            text("SELECT endpoint FROM bucket_secrets WHERE id = :id"),
            {"id": secret_id},
        )
        s3_endpoint = await connection.scalar(
            text("SELECT endpoint FROM bucket_secrets WHERE id = :id"),
            {"id": seeded_organization.bucket_secret.id},
        )
    assert azure_endpoint != CONNECTION_STRING
    assert decrypt(azure_endpoint) == CONNECTION_STRING
    assert s3_endpoint == seeded_organization.bucket_secret.endpoint

    await run_alembic(engine, "downgrade", "043")
    async with engine.connect() as connection:
        restored = await connection.scalar(
            text("SELECT endpoint FROM bucket_secrets WHERE id = :id"),
            {"id": secret_id},
        )
    assert restored == CONNECTION_STRING
    await run_alembic(engine, "upgrade", "head")
