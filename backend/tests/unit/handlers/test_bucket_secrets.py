import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from dataforce_studio.handlers import BucketSecretHandler
from dataforce_studio.infra.exceptions import (
    BucketSecretInUseError,
    DatabaseConstraintError,
    NotFoundError,
)
from dataforce_studio.schemas import (
    Action,
    BucketSecret,
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUrls,
    Resource,
)

handler = BucketSecretHandler()


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.create_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_bucket_secret(
    mock_check_organization_permission: AsyncMock,
    mock_create_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_create_in = BucketSecretCreateIn(
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    expected = BucketSecretOut(
        id="MbB5SVQKbqNMHhB2CT6oNs",
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
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
    )
    mock_create_bucket_secret.assert_awaited_once()


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_organization_bucket_secrets",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_bucket_secrets(
    mock_check_organization_permission: AsyncMock,
    mock_get_organization_bucket_secrets: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    expected = [
        BucketSecretOut(
            id="MbB5SVQKbqNMHhB2CT6oNs",
            organization_id=organization_id,
            endpoint="s3.amazonaws.com",
            bucket_name="test-bucket-1",
            region="us-east-1",
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_get_organization_bucket_secrets.return_value = expected

    secrets = await handler.get_organization_bucket_secrets(user_id, organization_id)

    assert secrets == expected
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
    )
    mock_get_organization_bucket_secrets.assert_awaited_once_with(organization_id)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret(
    mock_check_organization_permission: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"
    expected = BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        region="us-east-1",
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_bucket_secret.return_value = expected

    secret = await handler.get_bucket_secret(user_id, organization_id, secret_id)

    assert secret == expected
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_secret_not_found(
    mock_check_organization_permission: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError, match="Secret not found") as error:
        await handler.get_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret(
    mock_check_organization_permission: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"
    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )
    expected = BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
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
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.update_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_bucket_secret_not_found(
    mock_check_organization_permission: AsyncMock,
    mock_update_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"
    secret_update = BucketSecretUpdate(
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
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret(
    mock_check_organization_permission: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"

    await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    mock_delete_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.delete_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.PermissionsHandler.check_organization_permission",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_bucket_secret_in_use(
    mock_check_organization_permission: AsyncMock,
    mock_delete_bucket_secret: AsyncMock,
) -> None:
    user_id = "cLZHBYAXuzDCWTTQ9ouoXa"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"

    mock_delete_bucket_secret.side_effect = DatabaseConstraintError()

    with pytest.raises(BucketSecretInUseError) as error:
        await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 409
    mock_delete_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch("dataforce_studio.handlers.bucket_secrets.S3Service")
@pytest.mark.asyncio
async def test_generate_bucket_urls(
    mock_s3_service: Mock,
) -> None:
    secret = BucketSecretCreateIn(
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

    mock_s3_instance = Mock()
    mock_s3_instance.get_upload_url = AsyncMock(return_value=presigned_url)
    mock_s3_instance.get_download_url = AsyncMock(return_value=download_url)
    mock_s3_instance.get_delete_url = AsyncMock(return_value=delete_url)
    mock_s3_service.return_value = mock_s3_instance

    urls = await handler.generate_bucket_urls(secret)

    assert urls == expected
    mock_s3_service.assert_called_once_with(secret)
    mock_s3_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_s3_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_s3_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch("dataforce_studio.handlers.bucket_secrets.S3Service")
@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls(
    mock_get_bucket_secret: AsyncMock,
    mock_s3_service: Mock,
) -> None:
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"
    organization_id = "k3vQLigRVfjA4maDMkeTow"
    original_secret = BucketSecret(
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
    secret = BucketSecretUpdate(
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

    mock_s3_instance = Mock()
    mock_s3_instance.get_upload_url = AsyncMock(return_value=presigned_url)
    mock_s3_instance.get_download_url = AsyncMock(return_value=download_url)
    mock_s3_instance.get_delete_url = AsyncMock(return_value=delete_url)
    mock_s3_service.return_value = mock_s3_instance
    mock_get_bucket_secret.return_value = original_secret

    urls = await handler.get_existing_bucket_urls(secret)

    assert urls == expected
    # The secret.id is now converted to full UUID, so we expect that
    mock_get_bucket_secret.assert_awaited_once_with(secret.id)
    mock_s3_service.assert_called_once()
    mock_s3_instance.get_upload_url.assert_awaited_once_with(object_name)
    mock_s3_instance.get_download_url.assert_awaited_once_with(object_name)
    mock_s3_instance.get_delete_url.assert_awaited_once_with(object_name)


@patch(
    "dataforce_studio.handlers.bucket_secrets.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_existing_bucket_urls_secret_not_found(
    mock_get_bucket_secret: AsyncMock,
) -> None:
    secret_id = "MbB5SVQKbqNMHhB2CT6oNs"

    secret = BucketSecretUpdate(
        id=secret_id,
        bucket_name="new-bucket-name",
        access_key="new-access_key",
    )

    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError) as error:
        await handler.get_existing_bucket_urls(secret)

    assert error.value.status_code == 404
