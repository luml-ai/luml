from unittest.mock import AsyncMock, Mock

import pytest

from luml_api._exceptions import LumlAPIError
from luml_api._types import (
    BucketType,
    MultiPartUploadDetails,
    PartDetails,
    UploadDetails,
)
from luml_api.services.upload_service import AsyncUploadService, UploadService


def _multipart_details() -> MultiPartUploadDetails:
    return MultiPartUploadDetails(
        type=BucketType.S3,
        upload_id="upload-123",
        parts=[
            PartDetails(
                part_number=1,
                url="https://s3.example.com/part1",
                start_byte=0,
                end_byte=9,
                part_size=10,
            )
        ],
        complete_url="https://s3.example.com/complete",
    )


def test_upload_file_simple(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = Mock()
    handler.upload_simple.return_value = Mock(status_code=200)
    monkeypatch.setattr(
        "luml_api.services.upload_service.create_file_handler",
        Mock(return_value=handler),
    )
    upload_details = UploadDetails(
        type=BucketType.S3,
        url="https://s3.example.com/upload",
        multipart=False,
        bucket_location="loc",
        bucket_secret_id="secret-1",
    )
    progress = Mock()
    service = UploadService(Mock())

    result = service.upload_file(
        upload_details=upload_details,
        file_path="model.fnnx",
        file_size=10,
        file_name="model.fnnx",
        on_progress=progress,
    )

    assert result.status_code == 200
    assert handler.on_progress is progress
    handler.upload_simple.assert_called_once_with(
        url="https://s3.example.com/upload",
        file_path="model.fnnx",
        file_size=10,
        file_name="model.fnnx",
    )


def test_upload_file_simple_missing_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "luml_api.services.upload_service.create_file_handler",
        Mock(return_value=Mock()),
    )
    upload_details = UploadDetails(
        type=BucketType.S3,
        url=None,
        multipart=False,
        bucket_location="loc",
        bucket_secret_id="secret-1",
    )
    service = UploadService(Mock())

    with pytest.raises(LumlAPIError, match="Upload URL is required"):
        service.upload_file(
            upload_details=upload_details, file_path="model.fnnx", file_size=10
        )


def test_upload_file_multipart(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = Mock()
    handler.initiate_multipart_upload.return_value = "upload-123"
    handler.upload_multipart.return_value = Mock(status_code=200)
    monkeypatch.setattr(
        "luml_api.services.upload_service.create_file_handler",
        Mock(return_value=handler),
    )
    multipart = _multipart_details()
    bucket_secrets = Mock()
    bucket_secrets.get_multipart_upload_urls.return_value = multipart
    upload_details = UploadDetails(
        type=BucketType.S3,
        url="https://s3.example.com/initiate",
        multipart=True,
        bucket_location="loc",
        bucket_secret_id="secret-1",
    )
    service = UploadService(bucket_secrets)

    result = service.upload_file(
        upload_details=upload_details, file_path="model.fnnx", file_size=10
    )

    assert result.status_code == 200
    handler.initiate_multipart_upload.assert_called_once_with(
        "https://s3.example.com/initiate"
    )
    bucket_secrets.get_multipart_upload_urls.assert_called_once_with(
        "secret-1", "loc", 10, "upload-123"
    )
    handler.upload_multipart.assert_called_once_with(
        parts=multipart.parts,
        complete_url=multipart.complete_url,
        file_size=10,
        file_path="model.fnnx",
        file_name="",
        upload_id="upload-123",
    )


@pytest.mark.asyncio
async def test_async_upload_file_simple(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = Mock()
    handler.upload_simple.return_value = Mock(status_code=200)
    monkeypatch.setattr(
        "luml_api.services.upload_service.create_file_handler",
        Mock(return_value=handler),
    )
    upload_details = UploadDetails(
        type=BucketType.AZURE,
        url="https://blob.example.com/upload",
        multipart=False,
        bucket_location="loc",
        bucket_secret_id="secret-1",
    )
    service = AsyncUploadService(AsyncMock())

    result = await service.upload_file(
        upload_details=upload_details, file_path="model.fnnx", file_size=10
    )

    assert result.status_code == 200
    handler.upload_simple.assert_called_once_with(
        url="https://blob.example.com/upload",
        file_path="model.fnnx",
        file_size=10,
        file_name="",
    )


@pytest.mark.asyncio
async def test_async_upload_file_simple_missing_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "luml_api.services.upload_service.create_file_handler",
        Mock(return_value=Mock()),
    )
    upload_details = UploadDetails(
        type=BucketType.S3,
        url=None,
        multipart=False,
        bucket_location="loc",
        bucket_secret_id="secret-1",
    )
    service = AsyncUploadService(AsyncMock())

    with pytest.raises(LumlAPIError, match="Upload URL is required"):
        await service.upload_file(
            upload_details=upload_details, file_path="model.fnnx", file_size=10
        )


@pytest.mark.asyncio
async def test_async_upload_file_multipart(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = Mock()
    handler.initiate_multipart_upload.return_value = "upload-123"
    handler.upload_multipart.return_value = Mock(status_code=200)
    monkeypatch.setattr(
        "luml_api.services.upload_service.create_file_handler",
        Mock(return_value=handler),
    )
    multipart = _multipart_details()
    bucket_secrets = AsyncMock()
    bucket_secrets.get_multipart_upload_urls.return_value = multipart
    upload_details = UploadDetails(
        type=BucketType.S3,
        url="https://s3.example.com/initiate",
        multipart=True,
        bucket_location="loc",
        bucket_secret_id="secret-1",
    )
    service = AsyncUploadService(bucket_secrets)

    result = await service.upload_file(
        upload_details=upload_details, file_path="model.fnnx", file_size=10
    )

    assert result.status_code == 200
    bucket_secrets.get_multipart_upload_urls.assert_awaited_once_with(
        "secret-1", "loc", 10, "upload-123"
    )
    handler.upload_multipart.assert_called_once_with(
        parts=multipart.parts,
        complete_url=multipart.complete_url,
        file_size=10,
        file_path="model.fnnx",
        file_name="",
        upload_id="upload-123",
    )
