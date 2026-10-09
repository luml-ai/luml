import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from luml.handlers.bucket_secrets import BucketSecretHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.bucket_secrets import (
    BucketSecretUpdate,
    BucketSecretUrls,
    BucketType,
    S3BucketSecret,
    S3BucketSecretCreateIn,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.storage import (
    BucketMultipartUpload,
    PartDetails,
    S3MultiPartUploadDetails,
)

from tests.support.ids import ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.bucket_secrets.conftest import (
    FOREIGN_SECRET_ID,
    SECRET_ID,
    _scoped_get_bucket_secret,
)

OBJECT_NAME = "test_file"
PRESIGNED_URL = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
DOWNLOAD_URL = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
DELETE_URL = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"


class TestBucketSecretUrls:
    async def test_generate_bucket_urls_returns_presigned_urls(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret = S3BucketSecretCreateIn(
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket",
            access_key="access_key",
            secret_key="secret_key",
            region="us-east-1",
        )
        expected = BucketSecretUrls(
            presigned_url=PRESIGNED_URL,
            download_url=DOWNLOAD_URL,
            delete_url=DELETE_URL,
        )

        storage_instance = Mock()
        storage_instance.get_upload_url = AsyncMock(return_value=PRESIGNED_URL)
        storage_instance.get_download_url = AsyncMock(return_value=DOWNLOAD_URL)
        storage_instance.get_delete_url = AsyncMock(return_value=DELETE_URL)
        service_class = Mock(return_value=storage_instance)

        with patch(
            "luml.handlers.bucket_secrets.create_storage_client",
            return_value=service_class,
        ) as create_storage_client:
            urls = await mocks.handler.generate_bucket_urls(secret)

        assert urls == expected
        create_storage_client.assert_called_once_with(secret.type)
        service_class.assert_called_once_with(secret)
        storage_instance.get_upload_url.assert_awaited_once_with(OBJECT_NAME)
        storage_instance.get_download_url.assert_awaited_once_with(OBJECT_NAME)
        storage_instance.get_delete_url.assert_awaited_once_with(OBJECT_NAME)

    async def test_get_existing_bucket_urls_signs_stored_secret_merged_with_update(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        original_secret = S3BucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            endpoint="s3.amazonaws.com",
            bucket_name="original_name",
            access_key="access_key",
            secret_key="secret_key",
            session_token=None,
            secure=True,
            region="us-east-1",
            cert_check=None,
        )
        secret = BucketSecretUpdate(
            id=SECRET_ID,
            endpoint="new.s3.amazonaws.com",
            bucket_name="new-bucket-name",
            access_key="new-access_key",
        )
        expected = BucketSecretUrls(
            presigned_url=PRESIGNED_URL,
            download_url=DOWNLOAD_URL,
            delete_url=DELETE_URL,
        )

        storage_instance = Mock()
        storage_instance.get_upload_url = AsyncMock(return_value=PRESIGNED_URL)
        storage_instance.get_download_url = AsyncMock(return_value=DOWNLOAD_URL)
        storage_instance.get_delete_url = AsyncMock(return_value=DELETE_URL)
        service_class = Mock(return_value=storage_instance)
        mocks.secret_repository.get_bucket_secret.return_value = original_secret

        with patch(
            "luml.handlers.bucket_secrets.create_storage_client",
            return_value=service_class,
        ) as create_storage_client:
            urls = await mocks.handler.get_existing_bucket_urls(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret
            )

        assert urls == expected
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
        )
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        create_storage_client.assert_called_once()
        storage_instance.get_upload_url.assert_awaited_once_with(OBJECT_NAME)
        storage_instance.get_download_url.assert_awaited_once_with(OBJECT_NAME)
        storage_instance.get_delete_url.assert_awaited_once_with(OBJECT_NAME)

        (signed_secret,) = service_class.call_args.args
        assert signed_secret.endpoint == "new.s3.amazonaws.com"
        assert signed_secret.bucket_name == "new-bucket-name"
        assert signed_secret.access_key == "new-access_key"
        assert signed_secret.secret_key == original_secret.secret_key

    async def test_get_existing_bucket_urls_raises_bad_request_when_type_changes(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        original_secret = Mock(id=SECRET_ID, type=BucketType.S3)
        secret = BucketSecretUpdate(
            id=SECRET_ID,
            bucket_name="new-bucket-name",
            type=BucketType.AZURE,
        )

        mocks.secret_repository.get_bucket_secret.return_value = original_secret

        with (
            patch(
                "luml.handlers.bucket_secrets.create_storage_client"
            ) as create_storage_client,
            pytest.raises(ApplicationError) as error,
        ):
            await mocks.handler.get_existing_bucket_urls(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret
            )

        assert error.value.status_code == 400
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(
            SECRET_ID, ORGANIZATION_ID
        )
        create_storage_client.assert_not_called()

    async def test_get_existing_bucket_urls_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret = BucketSecretUpdate(
            id=SECRET_ID,
            bucket_name="new-bucket-name",
            access_key="new-access_key",
        )

        mocks.secret_repository.get_bucket_secret.return_value = None

        with pytest.raises(NotFoundError) as error:
            await mocks.handler.get_existing_bucket_urls(
                USER_ID, ORGANIZATION_ID, SECRET_ID, secret
            )

        assert error.value.status_code == 404

    async def test_get_bucket_urls_returns_presigned_urls(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        secret = S3BucketSecretCreateIn(
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket",
            access_key="access_key",
            secret_key="secret_key",
            region="us-east-1",
        )
        expected = BucketSecretUrls(
            presigned_url=PRESIGNED_URL,
            download_url=DOWNLOAD_URL,
            delete_url=DELETE_URL,
        )

        storage_instance = AsyncMock()
        storage_instance.get_upload_url.return_value = PRESIGNED_URL
        storage_instance.get_download_url.return_value = DOWNLOAD_URL
        storage_instance.get_delete_url.return_value = DELETE_URL
        service_class = Mock(return_value=storage_instance)

        with patch(
            "luml.handlers.bucket_secrets.create_storage_client",
            return_value=service_class,
        ) as create_storage_client:
            urls = await mocks.handler.get_bucket_urls(secret)

        assert urls == expected
        create_storage_client.assert_called_once_with(secret.type)
        service_class.assert_called_once_with(secret)
        storage_instance.get_upload_url.assert_awaited_once_with(OBJECT_NAME)
        storage_instance.get_download_url.assert_awaited_once_with(OBJECT_NAME)
        storage_instance.get_delete_url.assert_awaited_once_with(OBJECT_NAME)

    async def test_get_bucket_multipart_urls_returns_upload_details(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        bucket_location = "orbit/collection/model.tar.gz"
        file_size = 10485760
        upload_id = "upload_id"

        original_secret = S3BucketSecret(
            id=SECRET_ID,
            organization_id=ORGANIZATION_ID,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket",
            access_key="access_key",
            secret_key="secret_key",
            session_token=None,
            secure=True,
            region="us-east-1",
            cert_check=None,
        )
        data = BucketMultipartUpload(
            bucket_id=SECRET_ID,
            bucket_location=bucket_location,
            size=file_size,
            upload_id=upload_id,
        )
        expected = S3MultiPartUploadDetails(
            upload_id=upload_id,
            parts=[
                PartDetails(
                    part_number=1,
                    url="https://test-bucket.s3.amazonaws.com/orbit/collection/model.tar.gz?partNumber=1",
                    start_byte=0,
                    end_byte=5242879,
                    part_size=5242880,
                ),
                PartDetails(
                    part_number=2,
                    url="https://test-bucket.s3.amazonaws.com/orbit/collection/model.tar.gz?partNumber=2",
                    start_byte=5242880,
                    end_byte=10485759,
                    part_size=5242880,
                ),
            ],
            complete_url="https://test-bucket.s3.amazonaws.com/orbit/collection/model.tar.gz?complete",
        )

        storage_instance = Mock()
        storage_instance.create_multipart_upload = AsyncMock(return_value=expected)
        service_class = Mock(return_value=storage_instance)
        mocks.secret_repository.get_bucket_secret.return_value = original_secret

        with patch(
            "luml.handlers.bucket_secrets.create_storage_client",
            return_value=service_class,
        ) as create_storage_client:
            result = await mocks.handler.get_bucket_multipart_urls(USER_ID, data)

        assert result == expected
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(SECRET_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.BUCKET_SECRET, Action.READ
        )
        create_storage_client.assert_called_once_with(original_secret.type)
        service_class.assert_called_once_with(original_secret)
        storage_instance.create_multipart_upload.assert_awaited_once_with(
            bucket_location, file_size, upload_id
        )

    async def test_get_bucket_multipart_urls_raises_not_found_when_secret_is_missing(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        data = BucketMultipartUpload(
            bucket_id=SECRET_ID,
            bucket_location="orbit/collection/model.tar.gz",
            size=10485760,
            upload_id="upload_id",
        )

        mocks.secret_repository.get_bucket_secret.return_value = None

        with (
            patch(
                "luml.handlers.bucket_secrets.create_storage_client"
            ) as create_storage_client,
            pytest.raises(NotFoundError) as error,
        ):
            await mocks.handler.get_bucket_multipart_urls(USER_ID, data)

        assert error.value.status_code == 404
        mocks.secret_repository.get_bucket_secret.assert_awaited_once_with(SECRET_ID)
        create_storage_client.assert_not_called()

    async def test_get_existing_bucket_urls_rejects_body_id_differing_from_path(
        self, mocks: CollaboratorMocks[BucketSecretHandler]
    ) -> None:
        mocks.secret_repository.get_bucket_secret.side_effect = (
            _scoped_get_bucket_secret
        )

        with (
            patch(
                "luml.handlers.bucket_secrets.create_storage_client"
            ) as create_storage_client,
            pytest.raises(ApplicationError) as error,
        ):
            await mocks.handler.get_existing_bucket_urls(
                USER_ID,
                ORGANIZATION_ID,
                SECRET_ID,
                BucketSecretUpdate(id=FOREIGN_SECRET_ID),
            )

        assert error.value.status_code == 400
        mocks.secret_repository.get_bucket_secret.assert_not_called()
        create_storage_client.assert_not_called()
