from uuid import uuid7

import pytest
from luml.infra.encryption import decrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.alembic import run_alembic
from tests.support.bucket_secrets import CONNECTION_STRING, PUBLIC_ENDPOINT
from tests.support.seeds import OrganizationFixtureData


async def test_migration_encrypts_legacy_azure_secrets_and_preserves_s3(
    engine: AsyncEngine, seeded_organization: OrganizationFixtureData
) -> None:
    await run_alembic(engine, "downgrade", "042")
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
        azure = (
            await connection.execute(
                text(
                    "SELECT endpoint, connection_string FROM bucket_secrets "
                    "WHERE id = :id"
                ),
                {"id": secret_id},
            )
        ).one()
        s3 = (
            await connection.execute(
                text(
                    "SELECT endpoint, connection_string FROM bucket_secrets "
                    "WHERE id = :id"
                ),
                {"id": seeded_organization.bucket_secret.id},
            )
        ).one()
    assert azure.endpoint == PUBLIC_ENDPOINT
    assert azure.connection_string != CONNECTION_STRING
    assert decrypt(azure.connection_string) == CONNECTION_STRING
    assert s3.endpoint == seeded_organization.bucket_secret.endpoint
    assert s3.connection_string is None

    await run_alembic(engine, "downgrade", "042")
    async with engine.connect() as connection:
        restored = await connection.scalar(
            text("SELECT endpoint FROM bucket_secrets WHERE id = :id"),
            {"id": secret_id},
        )
    assert restored == CONNECTION_STRING
    await run_alembic(engine, "upgrade", "head")


async def test_migration_refuses_duplicate_azure_buckets_without_losing_data(
    engine: AsyncEngine, seeded_organization: OrganizationFixtureData
) -> None:
    await run_alembic(engine, "downgrade", "042")
    endpoints = [
        CONNECTION_STRING,
        CONNECTION_STRING.replace("dGVzdC1vbmx5LWtleQ==", "cm90YXRlZA=="),
    ]
    async with engine.begin() as connection:
        for endpoint in endpoints:
            await connection.execute(
                text(
                    "INSERT INTO bucket_secrets "
                    "(id, organization_id, type, endpoint, bucket_name, created_at) "
                    "VALUES (:id, :organization_id, 'azure', :endpoint, "
                    "'duplicate', now())"
                ),
                {
                    "id": uuid7(),
                    "organization_id": seeded_organization.organization.id,
                    "endpoint": endpoint,
                },
            )

    with pytest.raises(RuntimeError, match="Duplicate Azure buckets"):
        await run_alembic(engine, "upgrade", "head")

    async with engine.connect() as connection:
        stored = (
            await connection.scalars(
                text("SELECT endpoint FROM bucket_secrets WHERE type = 'azure'")
            )
        ).all()
        revision = await connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
    assert set(stored) == set(endpoints)
    assert revision == "042"
