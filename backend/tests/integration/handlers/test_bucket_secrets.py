from unittest.mock import AsyncMock

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.handlers.permissions import PermissionsHandler
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.schemas.bucket_secrets import (
    AzureBucketSecretCreate,
    BucketSecretUpdateIn,
    S3BucketSecretCreate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.bucket_secrets import CONNECTION_STRING
from tests.support.seeds import OrganizationFixtureData


@pytest.fixture
def handler(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> BucketSecretHandler:
    monkeypatch.setattr(
        BucketSecretHandler,
        "_BucketSecretHandler__secret_repository",
        BucketSecretRepository(engine),
    )
    monkeypatch.setattr(PermissionsHandler, "check_permissions", AsyncMock())
    return BucketSecretHandler()


class TestBucketSecretHandler:
    @pytest.mark.parametrize(
        "patch",
        [
            {"region": "eu-west-1"},
            {
                "endpoint": "s3-one.example.com",
                "bucket_name": "bucket-one",
                "region": "eu-west-1",
            },
            {},
            {"secure": False, "cert_check": False},
            {"session_token": None},
            {"secret_key": "rotated-test-secret"},
        ],
    )
    async def test_update_s3_secret_preserves_unspecified_fields(
        self,
        handler: BucketSecretHandler,
        seeded_organization: OrganizationFixtureData,
        patch: dict[str, str | bool | None],
    ) -> None:
        data = seeded_organization
        repository = BucketSecretRepository(data.engine)
        created = await repository.create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=data.organization.id,
                endpoint="s3-one.example.com",
                bucket_name="bucket-one",
                region="us-east-1",
                access_key="test-access",
                secret_key="test-secret",
                session_token="test-session",
                secure=True,
                cert_check=True,
            )
        )

        await handler.update_bucket_secret(
            data.user.id,
            data.organization.id,
            created.id,
            BucketSecretUpdateIn.model_validate(patch),
        )

        reloaded = await repository.get_bucket_secret(created.id, data.organization.id)
        assert reloaded is not None
        assert reloaded.model_dump(exclude={"updated_at"}) == (
            created.model_dump(exclude={"updated_at"}) | patch
        )

    async def test_update_azure_secret_preserves_unspecified_endpoint(
        self,
        handler: BucketSecretHandler,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        repository = BucketSecretRepository(data.engine)
        created = await repository.create_bucket_secret(
            AzureBucketSecretCreate(
                organization_id=data.organization.id,
                endpoint=CONNECTION_STRING,
                bucket_name="original-container",
            )
        )

        await handler.update_bucket_secret(
            data.user.id,
            data.organization.id,
            created.id,
            BucketSecretUpdateIn(bucket_name="updated-container"),
        )

        reloaded = await repository.get_bucket_secret(created.id, data.organization.id)
        assert reloaded is not None
        assert reloaded.model_dump(exclude={"updated_at"}) == (
            created.model_dump(exclude={"updated_at"})
            | {"bucket_name": "updated-container"}
        )
