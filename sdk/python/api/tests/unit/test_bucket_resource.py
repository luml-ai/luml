from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from luml_api._exceptions import LumlAPIError
from luml_api._types import BucketSecret, BucketSecretUrls
from luml_api.resources.bucket_secrets import (
    AsyncBucketSecretResource,
    BucketSecretResource,
)

PRESIGNED_URL = "https://bucket.example.com/upload?sig=abc"
DOWNLOAD_URL = "https://bucket.example.com/test-file"
DELETE_URL = "https://bucket.example.com/test-file?delete"


@pytest.fixture
def sample_bucket_secret_urls() -> BucketSecretUrls:
    return BucketSecretUrls(
        presigned_url=PRESIGNED_URL,
        download_url=DOWNLOAD_URL,
        delete_url=DELETE_URL,
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


def test_bucket_secret_list(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    mock_sync_client.get.return_value = [sample_bucket_secret.model_dump()]

    resource = BucketSecretResource(mock_sync_client)
    secrets = resource.list()

    mock_sync_client.get.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets"
    )
    assert len(secrets) == 1
    assert secrets[0].endpoint == sample_bucket_secret.endpoint


def test_bucket_secret_list_none_response(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = BucketSecretResource(mock_sync_client)
    secrets = resource.list()

    assert len(secrets) == 0


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


def test_bucket_secret_get_by_id(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    bucket_id = sample_bucket_secret.id
    mock_sync_client.get.return_value = sample_bucket_secret.model_dump()

    resource = BucketSecretResource(mock_sync_client)
    secret = resource.get(bucket_id)

    mock_sync_client.get.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets/{bucket_id}"
    )
    assert secret.id == bucket_id


def test_bucket_secret_get_by_name(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    mock_sync_client.get.return_value = [sample_bucket_secret.model_dump()]

    resource = BucketSecretResource(mock_sync_client)
    secret = resource.get(sample_bucket_secret.bucket_name)

    assert secret.bucket_name == sample_bucket_secret.bucket_name


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@patch.object(BucketSecretResource, "_check_bucket")
def test_bucket_secret_create(
    mock_check_bucket: Mock,
    mock_sync_client: Mock,
    sample_bucket_secret: BucketSecret,
) -> None:
    organization_id = mock_sync_client.organization
    mock_sync_client.post.return_value = sample_bucket_secret.model_dump()

    expected_json = {
        "endpoint": "s3.amazonaws.com",
        "bucket_name": "my-bucket",
        "region": "us-east-1",
        "access_key": "access_key",
        "secret_key": "secret_key",
        "type": "s3",
    }
    mock_sync_client.filter_none.return_value = expected_json

    resource = BucketSecretResource(mock_sync_client)
    resource.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-bucket",
        region="us-east-1",
        access_key="access_key",
        secret_key="secret_key",
    )

    mock_check_bucket.assert_called_once()
    mock_sync_client.post.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets",
        json=expected_json,
    )


@patch.object(BucketSecretResource, "_check_bucket")
def test_bucket_secret_create_skipped_when_check_fails(
    mock_check_bucket: Mock,
    mock_sync_client: Mock,
) -> None:
    mock_check_bucket.side_effect = LumlAPIError("Bucket Range Support check failed")

    resource = BucketSecretResource(mock_sync_client)
    with pytest.raises(LumlAPIError, match="Bucket Range Support check failed"):
        resource.create(
            endpoint="s3.amazonaws.com",
            bucket_name="my-bucket",
            region="us-east-1",
        )

    mock_sync_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------


def test_bucket_secret_update(
    mock_sync_client: Mock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_sync_client.organization
    bucket_id = sample_bucket_secret.id
    update_data = {"endpoint": "new.endpoint.com"}

    mock_sync_client.patch.return_value = sample_bucket_secret.model_dump()
    mock_sync_client.filter_none.return_value = update_data

    resource = BucketSecretResource(mock_sync_client)
    resource.update(bucket_id, endpoint=update_data["endpoint"])

    mock_sync_client.patch.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets/{bucket_id}",
        json=update_data,
    )


def test_bucket_secret_delete(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    secret_id = "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
    mock_sync_client.delete.return_value = None

    resource = BucketSecretResource(mock_sync_client)
    result = resource.delete(secret_id)

    mock_sync_client.delete.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets/{secret_id}"
    )
    assert result is None


# ---------------------------------------------------------------------------
# _validate_range_support
# ---------------------------------------------------------------------------


@patch("luml_api.resources.bucket_secrets.httpx.get")
def test_validate_range_support_success(mock_get: Mock) -> None:
    full_resp = Mock()
    full_resp.raise_for_status.return_value = None
    range_resp = Mock()
    range_resp.raise_for_status.return_value = None
    mock_get.side_effect = [full_resp, range_resp]

    BucketSecretResource._validate_range_support(DOWNLOAD_URL)

    assert mock_get.call_count == 2
    mock_get.assert_any_call(DOWNLOAD_URL)
    mock_get.assert_any_call(DOWNLOAD_URL, headers={"Range": "bytes=0-10"})


@patch("luml_api.resources.bucket_secrets.httpx.get")
def test_validate_range_support_full_download_fails(mock_get: Mock) -> None:
    full_resp = Mock()
    full_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=Mock(), response=Mock()
    )
    mock_get.return_value = full_resp

    with pytest.raises(httpx.HTTPStatusError):
        BucketSecretResource._validate_range_support(DOWNLOAD_URL)

    assert mock_get.call_count == 1


@patch("luml_api.resources.bucket_secrets.httpx.get")
def test_validate_range_support_range_request_fails(mock_get: Mock) -> None:
    full_resp = Mock()
    full_resp.raise_for_status.return_value = None
    range_resp = Mock()
    range_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=Mock(), response=Mock()
    )
    mock_get.side_effect = [full_resp, range_resp]

    with pytest.raises(httpx.HTTPStatusError):
        BucketSecretResource._validate_range_support(DOWNLOAD_URL)


# ---------------------------------------------------------------------------
# _check_bucket
# ---------------------------------------------------------------------------


@patch("luml_api.resources.bucket_secrets.httpx.delete")
@patch.object(BucketSecretResource, "_validate_range_support")
@patch("luml_api.resources.bucket_secrets.httpx.put")
@patch.object(BucketSecretResource, "_get_connection_urls")
def test_check_bucket_success(
    mock_get_urls: Mock,
    mock_put: Mock,
    mock_validate: Mock,
    mock_delete: Mock,
    mock_sync_client: Mock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls
    put_resp = Mock()
    put_resp.raise_for_status.return_value = None
    mock_put.return_value = put_resp

    resource = BucketSecretResource(mock_sync_client)
    resource._check_bucket(
        endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
    )

    mock_get_urls.assert_called_once()
    mock_put.assert_called_once_with(
        PRESIGNED_URL,
        content=b"Connection test.",
        headers={
            "Content-Type": "application/octet-stream",
            "x-ms-blob-type": "BlockBlob",
        },
    )
    mock_validate.assert_called_once_with(DOWNLOAD_URL)
    mock_delete.assert_called_once_with(DELETE_URL)


@patch.object(BucketSecretResource, "_get_connection_urls")
def test_check_bucket_get_connection_urls_fails(
    mock_get_urls: Mock,
    mock_sync_client: Mock,
) -> None:
    mock_get_urls.side_effect = Exception("network error")

    resource = BucketSecretResource(mock_sync_client)
    with pytest.raises(LumlAPIError, match="Failed to get connection string"):
        resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )


@patch.object(BucketSecretResource, "_get_connection_urls")
@patch("luml_api.resources.bucket_secrets.httpx.put")
def test_check_bucket_upload_fails_bad_status(
    mock_put: Mock,
    mock_get_urls: Mock,
    mock_sync_client: Mock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls
    put_resp = Mock()
    put_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=Mock(), response=Mock()
    )
    mock_put.return_value = put_resp

    resource = BucketSecretResource(mock_sync_client)
    with pytest.raises(LumlAPIError, match="Failed to upload test file"):
        resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )


@patch("luml_api.resources.bucket_secrets.httpx.delete")
@patch.object(BucketSecretResource, "_validate_range_support")
@patch("luml_api.resources.bucket_secrets.httpx.put")
@patch.object(BucketSecretResource, "_get_connection_urls")
def test_check_bucket_range_check_fails_deletes_file(
    mock_get_urls: Mock,
    mock_put: Mock,
    mock_validate: Mock,
    mock_delete: Mock,
    mock_sync_client: Mock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls
    put_resp = Mock()
    put_resp.raise_for_status.return_value = None
    mock_put.return_value = put_resp
    mock_validate.side_effect = Exception("range not supported")

    resource = BucketSecretResource(mock_sync_client)
    with pytest.raises(LumlAPIError, match="Bucket Range Support check failed"):
        resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )

    mock_delete.assert_called_once_with(DELETE_URL)


@patch("luml_api.resources.bucket_secrets.httpx.delete")
@patch.object(BucketSecretResource, "_validate_range_support")
@patch("luml_api.resources.bucket_secrets.httpx.put")
@patch.object(BucketSecretResource, "_get_connection_urls")
def test_check_bucket_range_check_fails_delete_error_suppressed(
    mock_get_urls: Mock,
    mock_put: Mock,
    mock_validate: Mock,
    mock_delete: Mock,
    mock_sync_client: Mock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls
    put_resp = Mock()
    put_resp.raise_for_status.return_value = None
    mock_put.return_value = put_resp
    mock_validate.side_effect = Exception("range not supported")
    mock_delete.side_effect = Exception("delete failed")

    resource = BucketSecretResource(mock_sync_client)
    with pytest.raises(LumlAPIError, match="Bucket Range Support check failed"):
        resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )


# ---------------------------------------------------------------------------
# Async: List / Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_bucket_secret_list(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    mock_async_client.get.return_value = [sample_bucket_secret.model_dump()]

    resource = AsyncBucketSecretResource(mock_async_client)
    secrets = await resource.list()

    mock_async_client.get.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets"
    )
    assert len(secrets) == 1
    assert secrets[0].endpoint == sample_bucket_secret.endpoint


@pytest.mark.asyncio
async def test_async_bucket_secret_get_by_id(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    secret_id = sample_bucket_secret.id
    mock_async_client.get.return_value = sample_bucket_secret.model_dump()

    resource = AsyncBucketSecretResource(mock_async_client)
    secret = await resource.get(secret_id)

    mock_async_client.get.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets/{secret_id}"
    )
    assert secret.id == secret_id


@pytest.mark.asyncio
async def test_async_bucket_secret_get_by_name(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    mock_async_client.get.return_value = [sample_bucket_secret.model_dump()]

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


# ---------------------------------------------------------------------------
# Async: Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch.object(AsyncBucketSecretResource, "_check_bucket", new_callable=AsyncMock)
async def test_async_bucket_secret_create(
    mock_check_bucket: AsyncMock,
    mock_async_client: AsyncMock,
    sample_bucket_secret: BucketSecret,
) -> None:
    organization_id = mock_async_client.organization
    mock_async_client.post.return_value = sample_bucket_secret.model_dump()

    expected_json = {
        "endpoint": "s3.amazonaws.com",
        "bucket_name": "my-bucket",
        "region": "us-east-1",
        "access_key": "access_key",
        "secret_key": "secret_key",
        "type": "s3",
    }
    mock_async_client.filter_none.return_value = expected_json

    resource = AsyncBucketSecretResource(mock_async_client)
    await resource.create(
        endpoint="s3.amazonaws.com",
        bucket_name="my-bucket",
        region="us-east-1",
        access_key="access_key",
        secret_key="secret_key",
    )

    mock_check_bucket.assert_called_once()
    mock_async_client.post.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets",
        json=expected_json,
    )


@pytest.mark.asyncio
@patch.object(AsyncBucketSecretResource, "_check_bucket", new_callable=AsyncMock)
async def test_async_bucket_secret_create_skipped_when_check_fails(
    mock_check_bucket: AsyncMock,
    mock_async_client: AsyncMock,
) -> None:
    mock_check_bucket.side_effect = LumlAPIError("Bucket Range Support check failed")

    resource = AsyncBucketSecretResource(mock_async_client)
    with pytest.raises(LumlAPIError, match="Bucket Range Support check failed"):
        await resource.create(
            endpoint="s3.amazonaws.com",
            bucket_name="my-bucket",
            region="us-east-1",
        )

    mock_async_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# Async: Update / Delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_bucket_secret_update(
    mock_async_client: AsyncMock, sample_bucket_secret: BucketSecret
) -> None:
    organization_id = mock_async_client.organization
    secret_id = sample_bucket_secret.id
    update_data = {"endpoint": "new.endpoint.com"}

    mock_async_client.patch.return_value = sample_bucket_secret.model_dump()
    mock_async_client.filter_none.return_value = update_data

    resource = AsyncBucketSecretResource(mock_async_client)
    await resource.update(secret_id, endpoint=update_data["endpoint"])

    mock_async_client.patch.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets/{secret_id}",
        json=update_data,
    )


@pytest.mark.asyncio
async def test_async_bucket_secret_delete(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    secret_id = "0199c455-21ef-79d9-9dfc-fec3d72bf4b5"
    mock_async_client.delete.return_value = None

    resource = AsyncBucketSecretResource(mock_async_client)
    result = await resource.delete(secret_id)

    mock_async_client.delete.assert_called_once_with(
        f"/v1/organizations/{organization_id}/bucket-secrets/{secret_id}"
    )
    assert result is None


# ---------------------------------------------------------------------------
# Async: _validate_range_support
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("luml_api.resources.bucket_secrets.httpx.AsyncClient")
async def test_async_validate_range_support_success(mock_client_class: Mock) -> None:
    mock_http = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_http
    mock_client_class.return_value.__aexit__.return_value = None

    full_resp = Mock()
    full_resp.raise_for_status.return_value = None
    range_resp = Mock()
    range_resp.raise_for_status.return_value = None
    mock_http.get.side_effect = [full_resp, range_resp]

    await AsyncBucketSecretResource._validate_range_support(DOWNLOAD_URL)

    assert mock_http.get.call_count == 2
    mock_http.get.assert_any_call(DOWNLOAD_URL)
    mock_http.get.assert_any_call(DOWNLOAD_URL, headers={"Range": "bytes=0-10"})


@pytest.mark.asyncio
@patch("luml_api.resources.bucket_secrets.httpx.AsyncClient")
async def test_async_validate_range_support_full_download_fails(
    mock_client_class: Mock,
) -> None:
    mock_http = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_http
    mock_client_class.return_value.__aexit__.return_value = None

    full_resp = Mock()
    full_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=Mock(), response=Mock()
    )
    mock_http.get.return_value = full_resp

    with pytest.raises(httpx.HTTPStatusError):
        await AsyncBucketSecretResource._validate_range_support(DOWNLOAD_URL)

    assert mock_http.get.call_count == 1


@pytest.mark.asyncio
@patch("luml_api.resources.bucket_secrets.httpx.AsyncClient")
async def test_async_validate_range_support_range_request_fails(
    mock_client_class: Mock,
) -> None:
    mock_http = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_http
    mock_client_class.return_value.__aexit__.return_value = None

    full_resp = Mock()
    full_resp.raise_for_status.return_value = None
    range_resp = Mock()
    range_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=Mock(), response=Mock()
    )
    mock_http.get.side_effect = [full_resp, range_resp]

    with pytest.raises(httpx.HTTPStatusError):
        await AsyncBucketSecretResource._validate_range_support(DOWNLOAD_URL)


# ---------------------------------------------------------------------------
# Async: _check_bucket
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch.object(
    AsyncBucketSecretResource, "_validate_range_support", new_callable=AsyncMock
)
@patch.object(AsyncBucketSecretResource, "_get_connection_urls", new_callable=AsyncMock)
@patch("luml_api.resources.bucket_secrets.httpx.AsyncClient")
async def test_async_check_bucket_success(
    mock_client_class: Mock,
    mock_get_urls: AsyncMock,
    mock_validate: AsyncMock,
    mock_async_client: AsyncMock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls

    mock_http = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_http
    mock_client_class.return_value.__aexit__.return_value = None
    put_resp = Mock()
    put_resp.raise_for_status.return_value = None
    mock_http.put.return_value = put_resp

    resource = AsyncBucketSecretResource(mock_async_client)
    await resource._check_bucket(
        endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
    )

    mock_get_urls.assert_called_once()
    mock_http.put.assert_called_once_with(
        PRESIGNED_URL,
        content=b"Connection test.",
        headers={
            "Content-Type": "application/octet-stream",
            "x-ms-blob-type": "BlockBlob",
        },
    )
    mock_validate.assert_called_once_with(DOWNLOAD_URL)
    mock_http.delete.assert_called_once_with(DELETE_URL)


@pytest.mark.asyncio
@patch.object(AsyncBucketSecretResource, "_get_connection_urls", new_callable=AsyncMock)
async def test_async_check_bucket_get_connection_urls_fails(
    mock_get_urls: AsyncMock,
    mock_async_client: AsyncMock,
) -> None:
    mock_get_urls.side_effect = Exception("network error")

    resource = AsyncBucketSecretResource(mock_async_client)
    with pytest.raises(LumlAPIError, match="Failed to get connection string"):
        await resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )


@pytest.mark.asyncio
@patch.object(AsyncBucketSecretResource, "_get_connection_urls", new_callable=AsyncMock)
@patch("luml_api.resources.bucket_secrets.httpx.AsyncClient")
async def test_async_check_bucket_upload_fails_bad_status(
    mock_client_class: Mock,
    mock_get_urls: AsyncMock,
    mock_async_client: AsyncMock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls

    mock_http = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_http
    mock_client_class.return_value.__aexit__.return_value = None
    put_resp = Mock()
    put_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=Mock(), response=Mock()
    )
    mock_http.put.return_value = put_resp

    resource = AsyncBucketSecretResource(mock_async_client)
    with pytest.raises(LumlAPIError, match="Failed to upload test file"):
        await resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )


@pytest.mark.asyncio
@patch.object(
    AsyncBucketSecretResource, "_validate_range_support", new_callable=AsyncMock
)
@patch.object(AsyncBucketSecretResource, "_get_connection_urls", new_callable=AsyncMock)
@patch("luml_api.resources.bucket_secrets.httpx.AsyncClient")
async def test_async_check_bucket_range_check_fails_deletes_file(
    mock_client_class: Mock,
    mock_get_urls: AsyncMock,
    mock_validate: AsyncMock,
    mock_async_client: AsyncMock,
    sample_bucket_secret_urls: BucketSecretUrls,
) -> None:
    mock_get_urls.return_value = sample_bucket_secret_urls

    mock_http = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_http
    mock_client_class.return_value.__aexit__.return_value = None
    put_resp = Mock()
    put_resp.raise_for_status.return_value = None
    mock_http.put.return_value = put_resp
    mock_validate.side_effect = Exception("range not supported")

    resource = AsyncBucketSecretResource(mock_async_client)
    with pytest.raises(LumlAPIError, match="Bucket Range Support check failed"):
        await resource._check_bucket(
            endpoint="s3.amazonaws.com", bucket_name="my-bucket", region="us-east-1"
        )

    mock_http.delete.assert_called_once_with(DELETE_URL)
