from uuid import uuid4

import pytest
from luml.infra.exceptions import DatabaseConstraintError
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.bucket_secrets import (
    BucketSecretUpdate,
    S3BucketSecret,
    S3BucketSecretCreate,
    S3BucketSecretOut,
)
from luml.schemas.orbit import OrbitCreateIn
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_sibling_organization
from tests.support.seeds import OrganizationFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> BucketSecretRepository:
    return BucketSecretRepository(engine)


class TestBucketSecretRepository:
    async def test_create_bucket_secret_stores_endpoint_without_protocol(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        endpoint = "s3.amazonaws.com"

        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint=f"https://{endpoint}",
            bucket_name="test-bucket-create",
            access_key="test_access_key",
            secret_key="test_secret_key",
            session_token="test_session_token",
            secure=True,
            region="us-east-1",
            cert_check=True,
        )

        created_secret = await repository.create_bucket_secret(secret_data)

        assert isinstance(created_secret, S3BucketSecret)
        assert created_secret.id
        assert created_secret.endpoint == endpoint
        assert created_secret.bucket_name == secret_data.bucket_name
        assert created_secret.organization_id == seeded_organization.organization.id
        assert created_secret.secure == secret_data.secure
        assert created_secret.region == secret_data.region
        assert created_secret.cert_check == secret_data.cert_check
        assert created_secret.created_at

    async def test_create_bucket_secret_raises_when_duplicate(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.duplicate.com",
            bucket_name="duplicate-bucket",
            region="us-east-1",
        )

        await repository.create_bucket_secret(secret_data)

        with pytest.raises(DatabaseConstraintError):
            await repository.create_bucket_secret(secret_data)

    async def test_get_bucket_secret_returns_stored_secret(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.get.com",
            bucket_name="test-bucket-get",
            region="us-east-1",
        )

        created_secret = await repository.create_bucket_secret(secret_data)
        fetched_secret = await repository.get_bucket_secret(
            created_secret.id, seeded_organization.organization.id
        )

        assert fetched_secret
        assert isinstance(fetched_secret, S3BucketSecret)
        assert fetched_secret.id == created_secret.id
        assert fetched_secret.endpoint == created_secret.endpoint
        assert fetched_secret.bucket_name == created_secret.bucket_name

    async def test_get_bucket_secret_returns_none_when_missing(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        fetched_secret = await repository.get_bucket_secret(uuid4())

        assert fetched_secret is None

    async def test_get_bucket_secret_details_returns_stored_secret(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.details.com",
            bucket_name="test-bucket-details",
            region="us-east-1",
        )
        created_secret = await repository.create_bucket_secret(secret_data)

        details = await repository.get_bucket_secret_details(
            created_secret.id, seeded_organization.organization.id
        )

        assert details is not None
        assert isinstance(details, S3BucketSecretOut)
        assert details.id == created_secret.id
        assert details.endpoint == created_secret.endpoint
        assert details.bucket_name == created_secret.bucket_name

    async def test_get_bucket_secret_details_returns_none_when_missing(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        details = await repository.get_bucket_secret_details(
            uuid4(), seeded_organization.organization.id
        )

        assert details is None

    async def test_get_organization_bucket_secrets_returns_created_and_seeded_secrets(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        for i in range(5):
            secret_data = S3BucketSecretCreate(
                organization_id=seeded_organization.organization.id,
                endpoint=f"s3.test{i}.com",
                bucket_name=f"test-bucket-{i}",
                region="us-east-1",
            )
            await repository.create_bucket_secret(secret_data)

        secrets = await repository.get_organization_bucket_secrets(
            seeded_organization.organization.id
        )

        assert secrets
        assert isinstance(secrets, list)
        assert len(secrets) == 6
        assert all(isinstance(s, S3BucketSecretOut) for s in secrets)
        assert all(
            s.organization_id == seeded_organization.organization.id for s in secrets
        )

    async def test_update_bucket_secret_applies_given_fields(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        endpoint = "s3.update.com"

        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint=endpoint,
            bucket_name="test-bucket-update",
            region="us-east-1",
        )

        created_secret = await repository.create_bucket_secret(secret_data)
        assert isinstance(created_secret, S3BucketSecret)

        new_bucket_name = "updated-bucket-name"
        new_region = "eu-west-1"
        update_data = BucketSecretUpdate(
            id=created_secret.id,
            bucket_name=new_bucket_name,
            region=new_region,
            endpoint=f"https://{endpoint}",
        )

        updated_secret = await repository.update_bucket_secret(
            update_data, seeded_organization.organization.id
        )

        assert isinstance(updated_secret, S3BucketSecret)
        assert updated_secret.id == created_secret.id
        assert updated_secret.bucket_name == new_bucket_name
        assert updated_secret.region == new_region
        assert updated_secret.endpoint == endpoint

    async def test_update_bucket_secret_accepts_new_s3_credentials(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.credentials.com",
            bucket_name="test-bucket-credentials",
            region="us-east-1",
        )
        created_secret = await repository.create_bucket_secret(secret_data)

        update_data = BucketSecretUpdate(
            id=created_secret.id,
            access_key="new_access_key",
            secret_key="new_secret_key",
            session_token="new_session_token",
        )

        updated_secret = await repository.update_bucket_secret(
            update_data, seeded_organization.organization.id
        )

        assert updated_secret is not None
        assert updated_secret.id == created_secret.id

    async def test_update_bucket_secret_strips_http_protocol(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.update-strip.com",
            bucket_name="test-bucket-update-strip",
            region="us-east-1",
        )

        created_secret = await repository.create_bucket_secret(secret_data)

        update_data = BucketSecretUpdate(
            id=created_secret.id,
            endpoint="https://s3.new-endpoint.com",
        )

        updated_secret = await repository.update_bucket_secret(
            update_data, seeded_organization.organization.id
        )

        assert updated_secret
        assert updated_secret.endpoint == "s3.new-endpoint.com"

    async def test_update_bucket_secret_returns_none_when_missing(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        update_data = BucketSecretUpdate(
            id=uuid4(),
            bucket_name="new-name",
        )

        updated_secret = await repository.update_bucket_secret(
            update_data, seeded_organization.organization.id
        )

        assert updated_secret is None

    async def test_update_bucket_secret_raises_when_duplicate(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        second_secret = await repository.create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=seeded_organization.organization.id,
                endpoint="s3.second.com",
                bucket_name="second-bucket",
                region="us-east-1",
            )
        )

        update_data = BucketSecretUpdate(
            id=second_secret.id,
            endpoint=seeded_organization.bucket_secret.endpoint,
            bucket_name=seeded_organization.bucket_secret.bucket_name,
        )

        with pytest.raises(DatabaseConstraintError):
            await repository.update_bucket_secret(
                update_data, seeded_organization.organization.id
            )

    async def test_delete_bucket_secret_removes_secret(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.delete.com",
            bucket_name="test-bucket-delete",
            region="us-east-1",
        )

        created_secret = await repository.create_bucket_secret(secret_data)

        assert await repository.delete_bucket_secret(
            created_secret.id, seeded_organization.organization.id
        )

        fetched_secret = await repository.get_bucket_secret(created_secret.id)
        assert fetched_secret is None

    async def test_delete_bucket_secret_raises_when_used_by_orbit(
        self,
        repository: BucketSecretRepository,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        secret_data = S3BucketSecretCreate(
            organization_id=seeded_organization.organization.id,
            endpoint="s3.in-use.com",
            bucket_name="in-use-bucket",
            region="us-east-1",
        )
        created_secret = await repository.create_bucket_secret(secret_data)

        orbit_data = OrbitCreateIn(
            name="test orbit", bucket_secret_id=created_secret.id
        )
        await OrbitRepository(engine).create_orbit(
            seeded_organization.organization.id, orbit_data
        )

        with pytest.raises(DatabaseConstraintError):
            await repository.delete_bucket_secret(
                created_secret.id, seeded_organization.organization.id
            )

    async def test_get_bucket_secret_returns_none_when_organization_differs(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_organization.engine, seeded_organization.user.id
        )

        assert (
            await repository.get_bucket_secret(
                seeded_organization.bucket_secret.id, other_organization.id
            )
            is None
        )
        assert (
            await repository.get_bucket_secret(
                seeded_organization.bucket_secret.id,
                seeded_organization.organization.id,
            )
            is not None
        )

    async def test_get_bucket_secret_details_returns_none_when_organization_differs(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_organization.engine, seeded_organization.user.id
        )

        assert (
            await repository.get_bucket_secret_details(
                seeded_organization.bucket_secret.id, other_organization.id
            )
            is None
        )
        assert (
            await repository.get_bucket_secret_details(
                seeded_organization.bucket_secret.id,
                seeded_organization.organization.id,
            )
            is not None
        )

    async def test_update_bucket_secret_returns_none_when_organization_differs(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_organization.engine, seeded_organization.user.id
        )

        result = await repository.update_bucket_secret(
            BucketSecretUpdate(
                id=seeded_organization.bucket_secret.id,
                endpoint="other.s3.com",
                bucket_name="other-bucket",
                access_key="other-access-key",
            ),
            other_organization.id,
        )

        assert result is None

        untouched = await repository.get_bucket_secret(
            seeded_organization.bucket_secret.id, seeded_organization.organization.id
        )
        assert untouched
        assert untouched.endpoint == seeded_organization.bucket_secret.endpoint
        assert untouched.bucket_name == seeded_organization.bucket_secret.bucket_name

    async def test_delete_bucket_secret_returns_false_when_organization_differs(
        self,
        repository: BucketSecretRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_organization.engine, seeded_organization.user.id
        )

        assert (
            await repository.delete_bucket_secret(
                seeded_organization.bucket_secret.id, other_organization.id
            )
            is False
        )
        assert (
            await repository.get_bucket_secret(
                seeded_organization.bucket_secret.id,
                seeded_organization.organization.id,
            )
            is not None
        )
