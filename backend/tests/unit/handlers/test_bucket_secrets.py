import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

from dataforce_studio.handlers.bucket_secrets import BucketSecretHandler
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    BucketSecretInUseError,
    DatabaseConstraintError,
    NotFoundError,
)
from dataforce_studio.schemas.bucket_secrets import (
    AzureBucketSecretCreate,
    AzureBucketSecretCreateIn,
    AzureBucketSecretOut,
    AzureBucketSecretUpdate,
    BucketSecretUrls,
    BucketType,
    S3BucketSecret,
    S3BucketSecretCreateIn,
    S3BucketSecretOut,
    S3BucketSecretUpdate,
)
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.schemas.storage import (
    BucketMultipartUpload,
    PartDetails,
    S3MultiPartUploadDetails,
)

handler = BucketSecretHandler()


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_create_in = S3BucketSecretCreateIn(
        type=BucketType.S3,
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    expected = S3BucketSecretOut(
        id=secret_id,
        type=secret_create_in.type,
        organization_id=organization_id,
        endpoint=secret_create_in.endpoint,
        bucket_name=secret_create_in.bucket_name,
        region=secret_create_in.region,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_create_bucket_secret.return_value = expected

    secret = await handler.create_bucket_secret(
        user_id, organization_id, secret_create_in
    )

    assert secret == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret_azure(
    mock_check_permissions: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_create_in = AzureBucketSecretCreateIn(
        type=BucketType.AZURE,
        endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
        bucket_name="test-bucket",
    )
    expected = AzureBucketSecretOut(
        id=secret_id,
        type=secret_create_in.type,
        organization_id=organization_id,
        endpoint=secret_create_in.endpoint,
        bucket_name=secret_create_in.bucket_name,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_create_bucket_secret.return_value = expected

    secret = await handler.create_bucket_secret(
        user_id, organization_id, secret_create_in
    )

    assert secret == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret_s3_not_unique(
    mock_check_permissions: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    secret_create_in = AzureBucketSecretCreateIn(
        type=BucketType.AZURE,
        endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
        bucket_name="test-bucket",
    )

    secret_create = AzureBucketSecretCreate(
        type=secret_create_in.type,
        organization_id=organization_id,
        endpoint=secret_create_in.endpoint,
        bucket_name=secret_create_in.bucket_name,
    )

    mock_create_bucket_secret.side_effect = DatabaseConstraintError(status_code=409)

    with pytest.raises(
        ApplicationError,
        match="Bucket secret with the given bucket name and endpoint already exists.",
    ) as error:
        await handler.create_bucket_secret(user_id, organization_id, secret_create_in)

    assert error.value.status_code == 409
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once_with(secret_create)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_organization_bucket_secrets",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_bucket_secrets(
    mock_check_permissions: AsyncMock,
    mock_get_organization_bucket_secrets: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    expected = [
        S3BucketSecretOut(
            id=secret_id,
            organization_id=organization_id,
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket-1",
            region="us-east-1",
            type=BucketType.S3,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_get_organization_bucket_secrets.return_value = expected

    secrets = await handler.get_organization_bucket_secrets(user_id, organization_id)

    assert secrets == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
    )
    mock_get_organization_bucket_secrets.assert_awaited_once_with(organization_id)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    expected = S3BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        region="us-east-1",
        type=BucketType.S3,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_bucket_secret.return_value = expected

    secret = await handler.get_bucket_secret(user_id, organization_id, secret_id)

    assert secret == expected
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError, match="Secret not found") as error:
        await handler.get_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = S3BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )
    expected = S3BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
        region="us-east-1",
        type=BucketType.S3,
        endpoint=secret_update.endpoint or "default-endpoint",
        bucket_name=secret_update.bucket_name or "default-bucket",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    mock_update_bucket_secret.return_value = expected

    secret = await handler.update_bucket_secret(
        user_id, organization_id, secret_id, secret_update
    )

    assert secret == expected
    assert secret_update.id == secret_id
    mock_update_bucket_secret.assert_awaited_once_with(secret_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_s3_not_unique(
    mock_check_permissions: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = AzureBucketSecretUpdate(
        id=secret_id,
        type=BucketType.AZURE,
        endpoint="DefaultEndpointsProtocol=https;AccountName=testbucket;AccountKey=+l0j8/86NqqQbn8oZReRUDCEkmGLBJS+AStrrQv9Q==;EndpointSuffix=core.windows.net",
        bucket_name="test-bucket",
    )

    mock_update_bucket_secret.side_effect = DatabaseConstraintError(status_code=409)

    with pytest.raises(
        ApplicationError,
        match="Bucket secret with the given bucket name and endpoint already exists.",
    ) as error:
        await handler.update_bucket_secret(
            user_id, organization_id, secret_id, secret_update
        )

    assert error.value.status_code == 409
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )
    mock_update_bucket_secret.assert_awaited_once_with(secret_update)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_not_found(
    mock_check_permissions: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret_update = S3BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )

    mock_update_bucket_secret.return_value = None

    with pytest.raises(NotFoundError, match="Secret not found") as error:
        await handler.update_bucket_secret(
            user_id, organization_id, secret_id, secret_update
        )

    assert error.value.status_code == 404
    assert secret_update.id == secret_id
    mock_update_bucket_secret.assert_awaited_once_with(secret_update)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret(
    mock_check_permissions: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    mock_delete_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret_in_use(
    mock_check_permissions: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_delete_bucket_secret.side_effect = DatabaseConstraintError()

    with pytest.raises(BucketSecretInUseError) as error:
        await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 409
    mock_delete_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch("dataforce_studio.handlers.bucket_secrets.create_storage_client")
@pytest.mark.asyncio
async def test_generate_bucket_urls(
    mock_create_storage_client: Mock,
) -> None:
    secret = S3BucketSecretCreateIn(
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    object_name = "test_file"

    presigned_url = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
    download_url = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
    delete_url = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"

    expected = BucketSecretUrls(
        presigned_url=presigned_url,
        download_url=download_url,
        delete_url=delete_url,
    )

    mock_storage_instance = Mock()
    mock_storage_instance.get_upload_url = AsyncMock(return_value=presigned_url)
    mock_storage_instance.get_download_url = AsyncMock(return_value=download_url)
    mock_storage_instance.get_delete_url = AsyncMock(return_value=delete_url)

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class

    urls = await handler.generate_bucket_urls(secret)

    assert urls == expected
    mock_create_storage_client.assert_called_once_with(secret.type)
    mock_service_class.assert_called_once_with(secret)
    mock_storage_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch("dataforce_studio.handlers.bucket_secrets.create_storage_client")
@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls(
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    original_secret = S3BucketSecret(
        id=secret_id,
        organization_id=organization_id,
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
    secret = S3BucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        access_key="new-access_key",
    )

    object_name = "test_file"

    presigned_url = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
    download_url = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
    delete_url = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"

    expected = BucketSecretUrls(
        presigned_url=presigned_url,
        download_url=download_url,
        delete_url=delete_url,
    )

    mock_storage_instance = Mock()
    mock_storage_instance.get_upload_url = AsyncMock(return_value=presigned_url)
    mock_storage_instance.get_download_url = AsyncMock(return_value=download_url)
    mock_storage_instance.get_delete_url = AsyncMock(return_value=delete_url)

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class
    mock_get_bucket_secret.return_value = original_secret

    urls = await handler.get_existing_bucket_urls(secret)

    assert urls == expected
    mock_get_bucket_secret.assert_awaited_once_with(secret.id)
    mock_create_storage_client.assert_called_once()
    mock_storage_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch("dataforce_studio.handlers.bucket_secrets.create_storage_client")
@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_type_cant_be_changed(
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    original_secret = Mock(id=secret_id, type=BucketType.S3)

    secret = AzureBucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        type=BucketType.AZURE,
    )

    mock_get_bucket_secret.return_value = original_secret

    with pytest.raises(ApplicationError) as error:
        await handler.get_existing_bucket_urls(secret)

    assert error.value.status_code == 400
    mock_get_bucket_secret.assert_awaited_once_with(secret.id)
    mock_create_storage_client.assert_not_called()


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_secret_not_found(
    mock_get_bucket_secret: AsyncMock,
) -> None:
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret = S3BucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        access_key="new-access_key",
    )

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError) as error:
        await handler.get_existing_bucket_urls(secret)

    assert error.value.status_code == 404


@patch("dataforce_studio.handlers.bucket_secrets.create_storage_client")
@pytest.mark.asyncio
async def test_get_bucket_urls(
    mock_create_storage_client: Mock,
) -> None:
    secret = S3BucketSecretCreateIn(
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    object_name = "test_file"

    presigned_url = "https://test-bucket.s3.amazonaws.com/test_file?presigned=true"
    download_url = "https://test-bucket.s3.amazonaws.com/test_file?download=true"
    delete_url = "https://test-bucket.s3.amazonaws.com/test_file?delete=true"

    expected = BucketSecretUrls(
        presigned_url=presigned_url,
        download_url=download_url,
        delete_url=delete_url,
    )

    mock_storage_instance = AsyncMock()
    mock_storage_instance.bucket_exists.return_value = True
    mock_storage_instance.get_upload_url.return_value = presigned_url
    mock_storage_instance.get_download_url.return_value = download_url
    mock_storage_instance.get_delete_url.return_value = delete_url

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class

    urls = await handler.get_bucket_urls(secret)

    assert urls == expected
    mock_create_storage_client.assert_called_once_with(secret.type)
    mock_service_class.assert_called_once_with(secret)
    mock_storage_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_storage_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch("dataforce_studio.handlers.bucket_secrets.create_storage_client")
@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_multipart_urls(
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    bucket_location = "orbit/collection/model.tar.gz"
    file_size = 10485760
    upload_id = "upload_id"

    original_secret = S3BucketSecret(
        id=secret_id,
        organization_id=organization_id,
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
        bucket_id=secret_id,
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

    mock_storage_instance = Mock()
    mock_storage_instance.create_multipart_upload = AsyncMock(return_value=expected)

    mock_service_class = Mock(return_value=mock_storage_instance)
    mock_create_storage_client.return_value = mock_service_class
    mock_get_bucket_secret.return_value = original_secret

    result = await handler.get_bucket_multipart_urls(data)

    assert result == expected
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)
    mock_create_storage_client.assert_called_once_with(original_secret.type)
    mock_service_class.assert_called_once_with(original_secret)
    mock_storage_instance.create_multipart_upload.assert_awaited_once_with(
        bucket_location, file_size, upload_id
    )


@patch("dataforce_studio.handlers.bucket_secrets.create_storage_client")
@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_multipart_urls_not_found(
    mock_get_bucket_secret: AsyncMock,
    mock_create_storage_client: Mock,
) -> None:
    secret_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    secret = S3BucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        access_key="new-access_key",
    )

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError) as error:
        await handler.get_existing_bucket_urls(secret)

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret.id)
    mock_create_storage_client.assert_not_called()
