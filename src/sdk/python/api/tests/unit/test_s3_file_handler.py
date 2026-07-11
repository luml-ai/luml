from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from respx import MockRouter

from luml_api._exceptions import FileUploadError, LumlAPIError
from luml_api._types import PartDetails
from luml_api.handlers.s3_file_handler import S3FileHandler
from luml_api.utils.progress import BaseProgressHandler

_UPLOAD_ID_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<InitiateMultipartUploadResult "
    'xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
    "<Bucket>test</Bucket><Key>model.fnnx</Key>"
    "<UploadId>upload-123</UploadId>"
    "</InitiateMultipartUploadResult>"
)


def _handler() -> S3FileHandler:
    handler = S3FileHandler()
    handler.on_progress = Mock(spec=BaseProgressHandler)
    return handler


@pytest.mark.respx
def test_upload_simple_success(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"payload-data")
    url = "https://s3.example.com/upload"
    route = respx_mock.put(url).mock(return_value=httpx.Response(200))
    handler = S3FileHandler()
    progress = Mock(spec=BaseProgressHandler)
    handler.on_progress = progress

    response = handler.upload_simple(url, str(file_path), file_size=12)

    assert response.status_code == 200
    assert route.called
    progress.finish.assert_called_once_with()


@pytest.mark.respx
def test_upload_simple_error_wrapped(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"payload")
    url = "https://s3.example.com/upload"
    respx_mock.put(url).mock(return_value=httpx.Response(500))
    handler = _handler()

    with pytest.raises(FileUploadError, match="Upload failed"):
        handler.upload_simple(url, str(file_path), file_size=7)


def test_upload_multipart_requires_upload_id() -> None:
    handler = _handler()
    with pytest.raises(ValueError, match="upload_id is required"):
        handler.upload_multipart(
            parts=[],
            complete_url="https://s3.example.com/complete",
            file_size=0,
            file_path="missing.bin",
        )


@pytest.mark.respx
def test_upload_multipart_success(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"0123456789")
    part_url_1 = "https://s3.example.com/part1"
    part_url_2 = "https://s3.example.com/part2"
    complete_url = "https://s3.example.com/complete"

    respx_mock.put(part_url_1).mock(
        return_value=httpx.Response(200, headers={"ETag": '"etag-1"'})
    )
    respx_mock.put(part_url_2).mock(
        return_value=httpx.Response(200, headers={"ETag": '"etag-2"'})
    )
    complete_route = respx_mock.post(complete_url).mock(
        return_value=httpx.Response(200)
    )

    parts = [
        PartDetails(
            part_number=1, url=part_url_1, start_byte=0, end_byte=4, part_size=5
        ),
        PartDetails(
            part_number=2, url=part_url_2, start_byte=5, end_byte=9, part_size=5
        ),
    ]
    handler = _handler()

    response = handler.upload_multipart(
        parts=parts,
        complete_url=complete_url,
        file_size=10,
        file_path=str(file_path),
        upload_id="upload-123",
    )

    assert response.status_code == 200
    assert complete_route.called
    body = complete_route.calls.last.request.content.decode()
    assert "<PartNumber>1</PartNumber><ETag>etag-1</ETag>" in body
    assert "<PartNumber>2</PartNumber><ETag>etag-2</ETag>" in body
    # part 1 must come before part 2 (sorted by part_number)
    assert body.index("etag-1") < body.index("etag-2")


@pytest.mark.respx
def test_upload_multipart_error_wrapped(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"01234")
    part_url = "https://s3.example.com/part1"
    respx_mock.put(part_url).mock(return_value=httpx.Response(403))
    parts = [
        PartDetails(part_number=1, url=part_url, start_byte=0, end_byte=4, part_size=5)
    ]
    handler = _handler()

    with pytest.raises(FileUploadError, match="Multipart upload failed"):
        handler.upload_multipart(
            parts=parts,
            complete_url="https://s3.example.com/complete",
            file_size=5,
            file_path=str(file_path),
            upload_id="upload-123",
        )


def test_upload_single_part_reads_correct_range(tmp_path: Path) -> None:
    with MockRouter(assert_all_called=False) as respx_mock:
        file_path = tmp_path / "model.fnnx"
        file_path.write_bytes(b"0123456789")
        part_url = "https://s3.example.com/part"
        route = respx_mock.put(part_url).mock(
            return_value=httpx.Response(200, headers={"ETag": '"abc"'})
        )
        part = PartDetails(
            part_number=3, url=part_url, start_byte=2, end_byte=5, part_size=4
        )
        updates: list[int] = []

        from threading import Lock

        result = S3FileHandler._upload_single_part(
            part, str(file_path), Lock(), updates.append
        )

        assert result == {"part_number": 3, "etag": "abc"}
        assert updates == [4]
        assert route.calls.last.request.content == b"2345"


@pytest.mark.respx
def test_initiate_multipart_upload_success(respx_mock: MockRouter) -> None:
    initiate_url = "https://s3.example.com/initiate"
    respx_mock.post(initiate_url).mock(
        return_value=httpx.Response(200, content=_UPLOAD_ID_XML.encode())
    )
    handler = _handler()

    upload_id = handler.initiate_multipart_upload(initiate_url)

    assert upload_id == "upload-123"


def test_initiate_multipart_upload_missing_url() -> None:
    handler = _handler()
    with pytest.raises(LumlAPIError, match="Upload URL is required"):
        handler.initiate_multipart_upload(None)


@pytest.mark.respx
def test_initiate_multipart_upload_missing_upload_id(respx_mock: MockRouter) -> None:
    initiate_url = "https://s3.example.com/initiate"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<InitiateMultipartUploadResult "
        'xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        "<Bucket>test</Bucket></InitiateMultipartUploadResult>"
    )
    respx_mock.post(initiate_url).mock(
        return_value=httpx.Response(200, content=xml.encode())
    )
    handler = _handler()

    with pytest.raises(LumlAPIError, match="Failed to initiate multipart upload"):
        handler.initiate_multipart_upload(initiate_url)
