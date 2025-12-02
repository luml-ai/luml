from unittest.mock import AsyncMock, Mock

import pytest

from luml.api._types import BucketSecret
from luml.api.resources.bucket_secrets import (
    AsyncBucketSecretResource,
    BucketSecretResource,
)


def test_bucket_secret_list(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    mock_sync_client.get.return_value = [sample_bucket_secret]

    resource = BucketSecretResource(mock_sync_client)
    secrets = resource.list()

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets"
    )
    assert len(secrets) == 1
    assert secrets[0].endpoint == sample_bucket_secret.endpoint


def test_bucket_secret_get_by_id(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    bucket_id = sample_bucket_secret.id
    mock_sync_client.get.return_value = sample_bucket_secret

    resource = BucketSecretResource(mock_sync_client)
    secret = resource.get(bucket_id)

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets/{bucket_id}"
    )
    assert secret.id == bucket_id


def test_bucket_secret_create(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    mock_sync_client.post.return_value = sample_bucket_secret

    expected_json = {
        "endpoint": "s3.amazonaws.com",
        "bucket_name": "my-bucket",
        "access_key": "access_key",
        "secret_key": "secret_key",
    }
    mock_sync_client.filter_none.return_value = expected_json

    resource = BucketSecretResource(mock_sync_client)
    resource.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-bucket",
        access_key="access_key",
        secret_key="secret_key",
    )

    mock_sync_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets",
        json=expected_json,
    )


def test_bucket_secret_update(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    bucket_id = sample_bucket_secret.id
    update_data = {"endpoint": "new.endpoint.com"}

    mock_sync_client.patch.return_value = sample_bucket_secret
    mock_sync_client.filter_none.return_value = update_data

    resource = BucketSecretResource(mock_sync_client)
    resource.update(bucket_id, endpoint=update_data["endpoint"])

    mock_sync_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets/{bucket_id}", json=update_data
    )


def test_bucket_secret_get_by_name(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    mock_sync_client.get.return_value = [sample_bucket_secret]

    resource = BucketSecretResource(mock_sync_client)
    secret = resource.get(sample_bucket_secret.bucket_name)

    assert secret.bucket_name == sample_bucket_secret.bucket_name


def test_bucket_secret_list_none_response(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = BucketSecretResource(mock_sync_client)
    secrets = resource.list()

    assert len(secrets) == 0


def test_bucket_secret_delete(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    secret_id = "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
    mock_sync_client.delete.return_value = None

    resource = BucketSecretResource(mock_sync_client)
    result = resource.delete(secret_id)

    mock_sync_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
    )
    assert result is None


# Async tests
@pytest.mark.asyncio
async def test_async_bucket_secret_list(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    mock_async_client.get.return_value = [sample_bucket_secret]

    resource = AsyncBucketSecretResource(mock_async_client)
    secrets = await resource.list()

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets"
    )
    assert len(secrets) == 1
    assert secrets[0].endpoint == sample_bucket_secret.endpoint


@pytest.mark.asyncio
async def test_async_bucket_secret_get_by_id(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    secret_id = sample_bucket_secret.id
    mock_async_client.get.return_value = sample_bucket_secret

    resource = AsyncBucketSecretResource(mock_async_client)
    secret = await resource.get(secret_id)

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
    )
    assert secret.id == secret_id


@pytest.mark.asyncio
async def test_async_bucket_secret_get_by_name(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    mock_async_client.get.return_value = [sample_bucket_secret]

    resource = AsyncBucketSecretResource(mock_async_client)
    secret = await resource.get(sample_bucket_secret.bucket_name)

    assert secret.bucket_name == sample_bucket_secret.bucket_name


@pytest.mark.asyncio
async def test_async_bucket_secret_list_none_response(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get.return_value = None

    resource = AsyncBucketSecretResource(mock_async_client)
    secrets = await resource.list()

    assert len(secrets) == 0


@pytest.mark.asyncio
async def test_async_bucket_secret_create(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    mock_async_client.post.return_value = sample_bucket_secret

    expected_json = {
        "endpoint": "s3.amazonaws.com",
        "bucket_name": "my-bucket",
        "access_key": "access_key",
        "secret_key": "secret_key",
    }
    mock_async_client.filter_none.return_value = expected_json

    resource = AsyncBucketSecretResource(mock_async_client)
    await resource.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-bucket",
        access_key="access_key",
        secret_key="secret_key",
    )

    mock_async_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets",
        json=expected_json,
    )


@pytest.mark.asyncio
async def test_async_bucket_secret_update(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    secret_id = sample_bucket_secret.id
    update_data = {"endpoint": "new.endpoint.com"}

    mock_async_client.patch.return_value = sample_bucket_secret
    mock_async_client.filter_none.return_value = update_data

    resource = AsyncBucketSecretResource(mock_async_client)
    await resource.update(secret_id, endpoint=update_data["endpoint"])

    mock_async_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets/{secret_id}", json=update_data
    )


@pytest.mark.asyncio
async def test_async_bucket_secret_delete(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    secret_id = "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
    mock_async_client.delete.return_value = None

    resource = AsyncBucketSecretResource(mock_async_client)
    result = await resource.delete(secret_id)

    mock_async_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/bucket-secrets/{secret_id}"
    )
    assert result is None
