import datetime

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.infra.exceptions import (
    BucketSecretInUseError,
    DatabaseConstraintError,
    NotFoundError,
)
from luml.schemas.bucket_secrets import (
    BucketSecretUpdate,
    BucketType,
    S3BucketSecret,
    S3BucketSecretCreateIn,
    S3BucketSecretOut,
)
from luml.schemas.permissions import Action, Resource

from tests.support.ids import ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.bucket_secrets.conftest import SECRET_ID


class TestBucketSecretS3:
    async def test_create_bucket_secret_returns_created_secret(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_create_in = S3BucketSecretCreateIn(
            type=BucketType.S3,
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket",
            access_key="access_key",
            secret_key="secret_key",
            region="us-east-1",
        )
        expected = S3BucketSecretOut(
            id=SECRET_ID,
            type=secret_create_in.type,
            organization_id=ORGANIZATION_ID,
            endpoint=secret_create_in.endpoint,
            bucket_name=secret_create_in.bucket_name,
            region=secret_create_in.region,
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

    async def test_get_organization_bucket_secrets_returns_secrets(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        expected = [
            S3BucketSecretOut(
                id=SECRET_ID,
                organization_id=ORGANIZATION_ID,
                endpoint="s3.amazonaws.com",
                bucket_name="test-bucket-1",
                region="us-east-1",
                type=BucketType.S3,
                created_at=datetime.datetime.now(),
                updated_at=None,
            )
        ]

        mocks.secret_repository.get_organization_bucket_secrets.return_value = expected

        secrets = await mocks.handler.get_organization_bucket_secrets(
            USER_ID, ORGANIZATION_ID
        )

        assert secrets == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.LIST
        )
        mocks.secret_repository.get_organization_bucket_secrets.assert_awaited_once_with(
            ORGANIZATION_ID
        )

    async def test_get_bucket_secret_returns_secret_details(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        expected = S3BucketSecretOut(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket",
            region="us-east-1",
            type=BucketType.S3,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.get_bucket_secret_details.return_value = expected

        secret = await mocks.handler.get_bucket_secret(
            USER_ID, ORGANIZATION_ID, SECRET_ID
        )

        assert secret == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
        )
        mocks.secret_repository.get_bucket_secret_details.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )

    async def test_get_bucket_secret_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.get_bucket_secret_details.return_value = None

        with pytest.raises(NotFoundError, match="Secret not found") as error:
            await mocks.handler.get_bucket_secret(USER_ID, ORGANIZATION_ID, SECRET_ID)

        assert error.value.status_code == 404
        mocks.secret_repository.get_bucket_secret_details.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
        )

    async def test_update_bucket_secret_returns_updated_secret(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_update = BucketSecretUpdate(
            id=SECRET_ID,
            endpoint="s3.amazonaws.com",
            bucket_name="updated-bucket",
        )
        existing = S3BucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            region="us-east-1",
            endpoint="original-endpoint",
            bucket_name="original-bucket",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
        expected = S3BucketSecretOut(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            region="us-east-1",
            type=BucketType.S3,
            endpoint=secret_update.endpoint or "default-endpoint",
            bucket_name=secret_update.bucket_name or "default-bucket",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )

        mocks.secret_repository.get_bucket_secret.return_value = existing
        mocks.secret_repository.update_bucket_secret.return_value = expected

        secret = await mocks.handler.update_bucket_secret(
            USER_ID, ORGANIZATION_ID, SECRET_ID, secret_update
        )

        assert secret == expected
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.secret_repository.update_bucket_secret.assert_awaited_once()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.UPDATE
        )

    async def test_update_bucket_secret_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_update = BucketSecretUpdate(
            id=SECRET_ID,
            endpoint="s3.amazonaws.com",
            bucket_name="updated-bucket",
        )

        mocks.secret_repository.get_bucket_secret.return_value = None

        with pytest.raises(NotFoundError, match="Secret not found") as error:
            await mocks.handler.update_bucket_secret(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret_update
            )

        assert error.value.status_code == 404
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.secret_repository.update_bucket_secret.assert_not_called()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.UPDATE
        )

    async def test_update_bucket_secret_raises_not_found_when_secret_vanishes(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret_update = BucketSecretUpdate(
            id=SECRET_ID,
            endpoint="s3.amazonaws.com",
            bucket_name="updated-bucket",
        )
        existing = S3BucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            region="us-east-1",
            endpoint="original-endpoint",
            bucket_name="original-bucket",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        mocks.secret_repository.get_bucket_secret.return_value = existing
        mocks.secret_repository.update_bucket_secret.return_value = None

        with pytest.raises(NotFoundError, match="Secret not found") as error:
            await mocks.handler.update_bucket_secret(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret_update
            )

        assert error.value.status_code == 404
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.secret_repository.update_bucket_secret.assert_awaited_once()

    async def test_delete_bucket_secret_deletes_by_id_and_organization(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.delete_bucket_secret.return_value = True

        await mocks.handler.delete_bucket_secret(USER_ID, ORGANIZATION_ID, SECRET_ID)

        mocks.secret_repository.delete_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.DELETE
        )

    async def test_delete_bucket_secret_raises_in_use_when_constraint_fails(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.delete_bucket_secret.side_effect = (
            DatabaseConstraintError()
        )

        with pytest.raises(BucketSecretInUseError) as error:
            await mocks.handler.delete_bucket_secret(
                USER_ID, ORGANIZATION_ID, SECRET_ID
            )

        assert error.value.status_code == 409
        mocks.secret_repository.delete_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.DELETE
        )
