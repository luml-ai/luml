from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from luml.clients.azure_storage_client import AzureBlobClient
from luml.clients.s3_storage_client import S3Client
from luml.constants import MAX_FILE_SIZE_BYTES
from luml.schemas.storage import BucketMultipartUpload
from pydantic import ValidationError


@pytest.mark.parametrize("size", [-1, 0, MAX_FILE_SIZE_BYTES + 1, 10**18])
def test_multipart_request_rejects_invalid_size(size: int) -> None:
    with pytest.raises(ValidationError):
        BucketMultipartUpload(
            bucket_id=uuid4(), bucket_location="model.luml", size=size, upload_id="id"
        )


@pytest.mark.parametrize("size", [1, 629145600, MAX_FILE_SIZE_BYTES])
def test_multipart_request_accepts_bounded_size(size: int) -> None:
    data = BucketMultipartUpload(
        bucket_id=uuid4(), bucket_location="model.luml", size=size, upload_id="id"
    )

    assert data.size == size


@pytest.mark.parametrize("client_type", [S3Client, AzureBlobClient])
async def test_multipart_client_rejects_oversize_before_signing(
    client_type: type[S3Client] | type[AzureBlobClient],
) -> None:
    client = client_type.__new__(client_type)
    with (
        patch.object(
            client, "_get_multipart_upload_urls", new_callable=AsyncMock
        ) as urls,
        patch.object(client, "get_complete_url", new_callable=AsyncMock) as complete,
        pytest.raises(ValueError, match="5TB"),
    ):
        await client.create_multipart_upload("model.luml", 10**18, "upload_id")

    urls.assert_not_awaited()
    complete.assert_not_awaited()


@pytest.mark.parametrize("client_type", [S3Client, AzureBlobClient])
async def test_multipart_client_accepts_maximum_size(
    client_type: type[S3Client] | type[AzureBlobClient],
) -> None:
    client = client_type.__new__(client_type)
    with (
        patch.object(
            client,
            "_get_multipart_upload_urls",
            new_callable=AsyncMock,
            return_value=[],
        ) as urls,
        patch.object(
            client,
            "get_complete_url",
            new_callable=AsyncMock,
            return_value="https://bucket/complete",
        ),
    ):
        await client.create_multipart_upload(
            "model.luml", MAX_FILE_SIZE_BYTES, "upload_id"
        )

    assert urls.await_args is not None
    assert urls.await_args.args[-1] == 5120
