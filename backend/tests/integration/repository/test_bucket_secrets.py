from uuid import uuid4

import pytest

from dataforce_studio.infra.exceptions import DatabaseConstraintError
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.schemas.bucket_secrets import (
    S3BucketSecret,
    S3BucketSecretCreate,
    S3BucketSecretUpdate,
)
from dataforce_studio.schemas.orbit import OrbitCreateIn
from tests.conftest import OrganizationFixtureData


@pytest.mark.asyncio
async def test_create_bucket_secret(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    endpoint = "s3.amazonaws.com"

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint=f"https://{endpoint}",
        bucket_name="test-bucket-create",
        access_key="test_access_key",
        secret_key="test_secret_key",
        session_token="test_session_token",
        secure=True,
        region="us-east-1",
        cert_check=True,
    )

    created_secret = await repo.create_bucket_secret(secret_data)

    assert created_secret
    assert created_secret.id
    assert created_secret.endpoint == endpoint
    assert created_secret.bucket_name == secret_data.bucket_name
    assert created_secret.organization_id == data.organization.id
    assert created_secret.secure == secret_data.secure
    assert created_secret.region == secret_data.region
    assert created_secret.cert_check == secret_data.cert_check
    assert created_secret.created_at


@pytest.mark.asyncio
async def test_create_duplicate_bucket_secret_raises_error(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint="s3.duplicate.com",
        bucket_name="duplicate-bucket",
        region="us-east-1",
    )

    await repo.create_bucket_secret(secret_data)

    with pytest.raises(DatabaseConstraintError):
        await repo.create_bucket_secret(secret_data)


@pytest.mark.asyncio
async def test_get_bucket_secret(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint="s3.get.com",
        bucket_name="test-bucket-get",
        region="us-east-1",
    )

    created_secret = await repo.create_bucket_secret(secret_data)
    fetched_secret = await repo.get_bucket_secret(created_secret.id)

    assert fetched_secret
    assert isinstance(fetched_secret, S3BucketSecret)
    assert fetched_secret.id == created_secret.id
    assert fetched_secret.endpoint == created_secret.endpoint
    assert fetched_secret.bucket_name == created_secret.bucket_name


@pytest.mark.asyncio
async def test_get_bucket_secret_not_found(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    repo = BucketSecretRepository(create_organization_with_user.engine)

    fetched_secret = await repo.get_bucket_secret(uuid4())

    assert fetched_secret is None


@pytest.mark.asyncio
async def test_get_organization_bucket_secrets(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    for i in range(5):
        secret_data = S3BucketSecretCreate(
            organization_id=data.organization.id,
            endpoint=f"s3.test{i}.com",
            bucket_name=f"test-bucket-{i}",
            region="us-east-1",
        )
        await repo.create_bucket_secret(secret_data)

    secrets = await repo.get_organization_bucket_secrets(data.organization.id)

    assert secrets
    assert isinstance(secrets, list)
    assert len(secrets) == 6  # The fixture creates one bucket-secret
    assert all(isinstance(s, S3BucketSecret) for s in secrets)
    assert all(s.organization_id == data.organization.id for s in secrets)


@pytest.mark.asyncio
async def test_update_bucket_secret(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)
    endpoint = "s3.update.com"

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint=endpoint,
        bucket_name="test-bucket-update",
        region="us-east-1",
    )

    created_secret = await repo.create_bucket_secret(secret_data)

    new_bucket_name = "updated-bucket-name"
    new_region = "eu-west-1"
    update_data = S3BucketSecretUpdate(
        id=created_secret.id,
        bucket_name=new_bucket_name,
        region=new_region,
        endpoint=f"https://{endpoint}",
    )

    updated_secret = await repo.update_bucket_secret(update_data)

    assert updated_secret
    assert updated_secret.id == created_secret.id
    assert updated_secret.bucket_name == new_bucket_name
    assert updated_secret.region == new_region
    assert updated_secret.endpoint == endpoint


@pytest.mark.asyncio
async def test_update_bucket_secret_strips_http_protocol(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint="s3.update-strip.com",
        bucket_name="test-bucket-update-strip",
        region="us-east-1",
    )

    created_secret = await repo.create_bucket_secret(secret_data)

    update_data = S3BucketSecretUpdate(
        id=created_secret.id,
        endpoint="https://s3.new-endpoint.com",
    )

    updated_secret = await repo.update_bucket_secret(update_data)

    assert updated_secret
    assert updated_secret.endpoint == "s3.new-endpoint.com"


@pytest.mark.asyncio
async def test_update_bucket_secret_not_found(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    non_existent_id = uuid4()
    update_data = S3BucketSecretUpdate(
        id=non_existent_id,
        bucket_name="new-name",
    )

    updated_secret = await repo.update_bucket_secret(update_data)

    assert updated_secret is None


@pytest.mark.asyncio
async def test_update_bucket_secret_duplicate_raises_error(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    secret1 = data.bucket_secret

    secret2_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint="s3.second.com",
        bucket_name="second-bucket",
        region="us-east-1",
    )
    secret2 = await repo.create_bucket_secret(secret2_data)

    update_data = S3BucketSecretUpdate(
        id=secret2.id,
        endpoint=secret1.endpoint,
        bucket_name=secret1.bucket_name,
    )

    with pytest.raises(DatabaseConstraintError):
        await repo.update_bucket_secret(update_data)


@pytest.mark.asyncio
async def test_delete_bucket_secret(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = BucketSecretRepository(data.engine)

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint="s3.delete.com",
        bucket_name="test-bucket-delete",
        region="us-east-1",
    )

    created_secret = await repo.create_bucket_secret(secret_data)

    await repo.delete_bucket_secret(created_secret.id)

    fetched_secret = await repo.get_bucket_secret(created_secret.id)
    assert fetched_secret is None


@pytest.mark.asyncio
async def test_delete_bucket_secret_in_use_raises_error(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    secret_repo = BucketSecretRepository(data.engine)
    orbit_repo = OrbitRepository(data.engine)

    secret_data = S3BucketSecretCreate(
        organization_id=data.organization.id,
        endpoint="s3.in-use.com",
        bucket_name="in-use-bucket",
        region="us-east-1",
    )
    created_secret = await secret_repo.create_bucket_secret(secret_data)

    orbit_data = OrbitCreateIn(name="test orbit", bucket_secret_id=created_secret.id)
    await orbit_repo.create_orbit(data.organization.id, orbit_data)

    with pytest.raises(DatabaseConstraintError):
        await secret_repo.delete_bucket_secret(created_secret.id)
