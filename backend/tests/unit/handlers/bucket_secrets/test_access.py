import datetime
from unittest.mock import patch
from uuid import UUID

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.infra.exceptions import InsufficientPermissionsError, NotFoundError
from luml.schemas.bucket_secrets import (
    AzureBucketSecret,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUpdateIn,
    S3BucketSecret,
    validate_bucket_secret_out,
)
from luml.schemas.permissions import Action, Resource

from tests.support.ids import ORGANIZATION_ID, OTHER_ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.bucket_secrets.conftest import (
    FOREIGN_SECRET_ID,
    SECRET_ID,
    _owner_s3_secret,
    _scoped_get_bucket_secret,
)


class TestBucketSecretAccess:
    async def test_get_bucket_secret_raises_not_found_for_foreign_organization(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        stored = _owner_s3_secret()

        async def scoped_details(
            secret_id: UUID, organization_id: UUID
        ) -> BucketSecretOut | None:
            if secret_id != stored.id or organization_id != stored.organization_id:
                return None
            return validate_bucket_secret_out(stored)

        mocks.secret_repository.get_bucket_secret_details.side_effect = scoped_details

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.get_bucket_secret(
                USER_ID, ORGANIZATION_ID, FOREIGN_SECRET_ID
            )

        assert error.value.status_code == 404
        assert str(error.value) == "Secret not found"
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
        )

    async def test_update_bucket_secret_raises_not_found_for_foreign_organization(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        stored = {FOREIGN_SECRET_ID: _owner_s3_secret()}

        async def scoped_get(
            secret_id: UUID, organization_id: UUID | None = None
        ) -> S3BucketSecret | None:
            secret = stored.get(secret_id)
            if not secret:
                return None
            if (
                organization_id is not None
                and secret.organization_id != organization_id
            ):
                return None
            return secret

        async def scoped_update(
            secret: BucketSecretUpdate, organization_id: UUID
        ) -> S3BucketSecret | None:
            if not await scoped_get(secret.id, organization_id):
                return None
            stored[secret.id] = stored[secret.id].model_copy(
                update=secret.model_dump(exclude_unset=True, exclude={"id"})
            )
            return stored[secret.id]

        mocks.secret_repository.get_bucket_secret.side_effect = scoped_get
        mocks.secret_repository.update_bucket_secret.side_effect = scoped_update

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.update_bucket_secret(
                USER_ID,
                ORGANIZATION_ID,
                FOREIGN_SECRET_ID,
                BucketSecretUpdateIn(
                    endpoint="other.s3.amazonaws.com",
                    bucket_name="other-bucket",
                    access_key="other-access-key",
                    secret_key="other-secret-key",
                    region="other-region",
                ),
            )

        assert error.value.status_code == 404
        assert str(error.value) == "Secret not found"
        mocks.secret_repository.update_bucket_secret.assert_not_called()

        owner_secret = stored[FOREIGN_SECRET_ID]
        assert owner_secret.endpoint == "owner.s3.amazonaws.com"
        assert owner_secret.bucket_name == "owner-bucket"
        assert owner_secret.access_key == "owner-access-key"
        assert owner_secret.secret_key == "owner-secret-key"
        assert owner_secret.region == "eu-west-1"

    async def test_update_bucket_secret_hides_azure_type_from_foreign_organization(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        stored = AzureBucketSecret(
            id=FOREIGN_SECRET_ID,
            organization_id=OTHER_ORGANIZATION_ID,
            endpoint="owner.blob.core.windows.net",
            bucket_name="owner-bucket",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )

        async def scoped_get(
            secret_id: UUID, organization_id: UUID | None = None
        ) -> AzureBucketSecret | None:
            if secret_id != stored.id:
                return None
            if (
                organization_id is not None
                and stored.organization_id != organization_id
            ):
                return None
            return stored

        mocks.secret_repository.get_bucket_secret.side_effect = scoped_get

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.update_bucket_secret(
                USER_ID,
                ORGANIZATION_ID,
                FOREIGN_SECRET_ID,
                BucketSecretUpdateIn(access_key="probe"),
            )

        assert error.value.status_code == 404
        mocks.secret_repository.update_bucket_secret.assert_not_called()

    async def test_delete_bucket_secret_raises_not_found_for_foreign_organization(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        stored = {FOREIGN_SECRET_ID: _owner_s3_secret()}

        async def scoped_delete(secret_id: UUID, organization_id: UUID) -> bool:
            secret = stored.get(secret_id)
            if not secret or secret.organization_id != organization_id:
                return False
            del stored[secret_id]
            return True

        mocks.secret_repository.delete_bucket_secret.side_effect = scoped_delete

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.delete_bucket_secret(
                USER_ID, ORGANIZATION_ID, FOREIGN_SECRET_ID
            )

        assert error.value.status_code == 404
        assert str(error.value) == "Secret not found"
        assert FOREIGN_SECRET_ID in stored

    async def test_delete_bucket_secret_raises_same_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.delete_bucket_secret.return_value = False

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.delete_bucket_secret(
                USER_ID, ORGANIZATION_ID, FOREIGN_SECRET_ID
            )

        assert error.value.status_code == 404
        assert str(error.value) == "Secret not found"

    async def test_get_existing_bucket_urls_raises_forbidden_before_loading_secret(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )
        mocks.secret_repository.get_bucket_secret.side_effect = (
            _scoped_get_bucket_secret
        )

        with (
            patch(
                "luml.handlers.bucket_secrets.create_storage_client"
            ) as create_storage_client,
            pytest.raises(InsufficientPermissionsError) as error,
        ):
            await mocks.handler.get_existing_bucket_urls(
                USER_ID,
                ORGANIZATION_ID,
                SECRET_ID,
                BucketSecretUpdate(id=SECRET_ID),
            )

        assert error.value.status_code == 403
        mocks.secret_repository.get_bucket_secret.assert_not_called()
        create_storage_client.assert_not_called()

    async def test_get_existing_bucket_urls_raises_not_found_for_foreign_organization(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.get_bucket_secret.side_effect = (
            _scoped_get_bucket_secret
        )

        with (
            patch(
                "luml.handlers.bucket_secrets.create_storage_client"
            ) as create_storage_client,
            pytest.raises(NotFoundError) as error,
        ):
            await mocks.handler.get_existing_bucket_urls(
                USER_ID,
                ORGANIZATION_ID,
                FOREIGN_SECRET_ID,
                BucketSecretUpdate(id=FOREIGN_SECRET_ID),
            )

        assert error.value.status_code == 404
        assert str(error.value) == "Secret not found"
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
        )
        create_storage_client.assert_not_called()
