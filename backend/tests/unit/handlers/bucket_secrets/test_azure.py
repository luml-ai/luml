import datetime
from unittest.mock import AsyncMock, patch

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.infra.exceptions import ApplicationError, DatabaseConstraintError
from luml.schemas.bucket_secrets import (
    AzureBucketSecret,
    AzureBucketSecretCreate,
    AzureBucketSecretCreateIn,
    AzureBucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUpdateIn,
    BucketType,
)
from luml.schemas.permissions import Action, Resource

from tests.support.bucket_secrets import CONNECTION_STRING, PUBLIC_ENDPOINT
from tests.support.ids import ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.bucket_secrets.conftest import SECRET_ID


class TestBucketSecretAzure:
    async def test_existing_azure_urls_preserve_credentials_for_public_endpoint(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        existing = AzureBucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            endpoint=CONNECTION_STRING,
            bucket_name="container",
            created_at=datetime.datetime.now(),
        )
        mocks.secret_repository.get_bucket_secret.return_value = existing
        with patch.object(
            mocks.handler, "generate_bucket_urls", new_callable=AsyncMock
        ) as generate:
            await mocks.handler.get_existing_bucket_urls(
                USER_ID,
                ORGANIZATION_ID,
                SECRET_ID,
                BucketSecretUpdate(
                    id=SECRET_ID, type=BucketType.AZURE, endpoint=PUBLIC_ENDPOINT
                ),
            )

        generate.assert_awaited_once_with(existing)

    @pytest.mark.parametrize("endpoint", [None, PUBLIC_ENDPOINT])
    async def test_azure_partial_update_preserves_unspecified_credentials(
        self, mocks: CollaboratorMocks[BucketSecretHandler], endpoint: str | None
    ) -> None:
        existing = AzureBucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            endpoint=CONNECTION_STRING,
            bucket_name="container",
            created_at=datetime.datetime.now(),
        )
        mocks.secret_repository.get_bucket_secret.return_value = existing
        mocks.secret_repository.update_bucket_secret.return_value = existing.model_copy(
            update={"bucket_name": "renamed"}
        )

        request = BucketSecretUpdateIn(bucket_name="renamed")
        if endpoint is not None:
            request.endpoint = endpoint
        result = await mocks.handler.update_bucket_secret(
            USER_ID,
            ORGANIZATION_ID,
            SECRET_ID,
            request,
        )

        update, _ = mocks.secret_repository.update_bucket_secret.call_args.args
        assert update.model_dump(exclude_unset=True) == {
            "id": SECRET_ID,
            "type": BucketType.AZURE,
            "bucket_name": "renamed",
        }
        assert result.endpoint == PUBLIC_ENDPOINT

    async def test_azure_update_rejects_invalid_connection_string_without_echoing_it(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.get_bucket_secret.return_value = AzureBucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            endpoint=CONNECTION_STRING,
            bucket_name="container",
            created_at=datetime.datetime.now(),
        )

        with pytest.raises(
            ApplicationError, match="Invalid Azure connection string"
        ) as error:
            await mocks.handler.update_bucket_secret(
                USER_ID,
                ORGANIZATION_ID,
                SECRET_ID,
                BucketSecretUpdateIn(endpoint=f"{CONNECTION_STRING};malformed"),
            )

        assert error.value.status_code == 400
        assert "AccountKey" not in error.value.message
        mocks.secret_repository.update_bucket_secret.assert_not_called()

    async def test_create_bucket_secret_returns_created_azure_secret(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_create_in = AzureBucketSecretCreateIn(
            type=BucketType.AZURE,
            endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
            bucket_name="test-bucket",
        )
        expected = AzureBucketSecretOut(
            id=SECRET_ID,
            type=secret_create_in.type,
            organization_id=ORGANIZATION_ID,
            endpoint=secret_create_in.endpoint,
            bucket_name=secret_create_in.bucket_name,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.create_bucket_secret.return_value = expected

        secret = await mocks.handler.create_bucket_secret(
            USER_ID, ORGANIZATION_ID, secret_create_in
        )

        assert secret == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.CREATE
        )
        mocks.secret_repository.create_bucket_secret.assert_awaited_once()

    async def test_create_bucket_secret_raises_conflict_when_azure_secret_exists(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_create_in = AzureBucketSecretCreateIn(
            type=BucketType.AZURE,
            endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
            bucket_name="test-bucket",
        )

        secret_create = AzureBucketSecretCreate(
            type=secret_create_in.type,
            organization_id=ORGANIZATION_ID,
            endpoint=secret_create_in.endpoint,
            bucket_name=secret_create_in.bucket_name,
        )

        mocks.secret_repository.create_bucket_secret.side_effect = (
            DatabaseConstraintError(status_code=409)
        )

        with pytest.raises(
            ApplicationError,
            match=(
                "Bucket secret with the given bucket name and endpoint already exists."
            ),
        ) as error:
            await mocks.handler.create_bucket_secret(
                USER_ID, ORGANIZATION_ID, secret_create_in
            )

        assert error.value.status_code == 409
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.CREATE
        )
        mocks.secret_repository.create_bucket_secret.assert_awaited_once_with(
            secret_create
        )

    async def test_update_bucket_secret_raises_conflict_when_azure_secret_exists(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_update = BucketSecretUpdate(
            id=SECRET_ID,
            endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
            bucket_name="test-bucket",
        )
        existing = AzureBucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            endpoint="original-endpoint",
            bucket_name="original-bucket",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.get_bucket_secret.return_value = existing
        mocks.secret_repository.update_bucket_secret.side_effect = (
            DatabaseConstraintError(status_code=409)
        )

        with pytest.raises(
            ApplicationError,
            match=(
                "Bucket secret with the given bucket name and endpoint already exists."
            ),
        ) as error:
            await mocks.handler.update_bucket_secret(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret_update
            )

        assert error.value.status_code == 409
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.UPDATE
        )
        mocks.secret_repository.update_bucket_secret.assert_awaited_once()

    async def test_update_bucket_secret_rejects_s3_fields_for_azure_secret(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_update = BucketSecretUpdate(
            id=SECRET_ID,
            endpoint="blob.core.windows.net",
            bucket_name="test-bucket",
            access_key="should-not-be-here",
        )
        existing = AzureBucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            endpoint="original-endpoint",
            bucket_name="original-bucket",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.get_bucket_secret.return_value = existing

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.update_bucket_secret(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret_update
            )

        assert error.value.status_code == 400
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.secret_repository.update_bucket_secret.assert_not_called()
