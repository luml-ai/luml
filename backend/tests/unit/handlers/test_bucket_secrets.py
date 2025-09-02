import datetime
from unittest.mock import AsyncMock, patch

import pytest

from dataforce_studio.handlers.bucket_secrets import BucketSecretHandler
from dataforce_studio.infra.exceptions import (
    BucketSecretInUseError,
    DatabaseConstraintError,
    NotFoundError,
)
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUrls,
)
from dataforce_studio.schemas.permissions import Action, Resource

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
    user_id = 1
    organization_id = 1
    secret_create_in = BucketSecretCreateIn(
        endpoint="s3.amazonaws.com",
        bucket_name="test-bucket",
        access_key="access_key",
        secret_key="secret_key",
        region="us-east-1",
    )
    expected = BucketSecretOut(
        id=1,
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
    user_id = 1
    organization_id = 1
    expected = [
        BucketSecretOut(
            id=1,
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
    user_id = 1
    organization_id = 1
    secret_id = 1
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
    user_id = 1
    organization_id = 1
    secret_id = 1

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
    user_id = 1
    organization_id = 1
    secret_id = 1
    secret_update = BucketSecretUpdate(
        id=secret_id,
        endpoint="s3.amazonaws.com",
        bucket_name="updated-bucket",
    )
    expected = BucketSecretOut(
        id=secret_id,
        organization_id=organization_id,
        endpoint=secret_update.endpoint,
        bucket_name=secret_update.bucket_name,
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
    user_id = 1
    organization_id = 1
    secret_id = 1
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
    user_id = 1
    organization_id = 1
    secret_id = 1

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
    user_id = 1
    organization_id = 1
    secret_id = 1

    mock_delete_bucket_secret.side_effect = DatabaseConstraintError()

    with pytest.raises(BucketSecretInUseError) as error:
        await handler.delete_bucket_secret(user_id, organization_id, secret_id)

    assert error.value.status_code == 409
    mock_delete_bucket_secret.assert_awaited_once_with(secret_id)
    mock_check_organization_permission.assert_awaited_once_with(
        organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
    )


@patch(
    "dataforce_studio.handlers.bucket_secrets.S3Service.get_delete_url",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.S3Service.get_download_url",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.bucket_secrets.S3Service.get_upload_url",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_bucket_urls(
    mock_get_upload_url: AsyncMock,
    mock_get_download_url: AsyncMock,
    mock_get_delete_url: AsyncMock,
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

    mock_get_upload_url.return_value = presigned_url
    mock_get_download_url.return_value = download_url
    mock_get_delete_url.return_value = delete_url

    urls = await handler.get_bucket_urls(secret)

    assert urls == expected
    mock_get_upload_url.assert_awaited_once_with(object_name)
    mock_get_download_url.assert_awaited_once_with(object_name)
    mock_get_delete_url.assert_awaited_once_with(object_name)
