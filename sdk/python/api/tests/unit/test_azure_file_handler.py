import base64
from pathlib import Path
from threading import Lock
from unittest.mock import Mock

import httpx
import pytest
from respx import MockRouter

from luml_api._exceptions import FileUploadError
from luml_api._types import PartDetails
from luml_api.handlers.azure_file_handler import AzureFileHandler
from luml_api.utils.progress import BaseProgressHandler


def _handler() -> AzureFileHandler:
    handler = AzureFileHandler()
    handler.on_progress = Mock(spec=BaseProgressHandler)
    return handler


def test_get_block_id_is_deterministic_base64() -> None:
    block_id = AzureFileHandler._get_block_id(7)
    assert block_id == base64.b64encode(b"block-00000007").decode()
    # padded to 8 digits and stable across calls
    assert AzureFileHandler._get_block_id(7) == block_id


@pytest.mark.respx
def test_upload_simple_success(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"payload-data")
    url = "https://blob.example.com/upload"
    route = respx_mock.put(url).mock(return_value=httpx.Response(201))
    handler = AzureFileHandler()
    progress = Mock(spec=BaseProgressHandler)
    handler.on_progress = progress

    response = handler.upload_simple(url, str(file_path), file_size=12)

    assert response.status_code == 201
    assert route.called
    assert route.calls.last.request.headers["x-ms-blob-type"] == "BlockBlob"
    progress.finish.assert_called_once_with()


@pytest.mark.respx
def test_upload_simple_error_wrapped(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"payload")
    url = "https://blob.example.com/upload"
    respx_mock.put(url).mock(return_value=httpx.Response(500))
    handler = _handler()

    with pytest.raises(FileUploadError, match="Upload failed"):
        handler.upload_simple(url, str(file_path), file_size=7)


@pytest.mark.respx
def test_upload_multipart_success(tmp_path: Path, respx_mock: MockRouter) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"0123456789")
    part_url_1 = "https://blob.example.com/part1"
    part_url_2 = "https://blob.example.com/part2"
    commit_url = "https://blob.example.com/commit"

    respx_mock.put(part_url_1).mock(return_value=httpx.Response(201))
    respx_mock.put(part_url_2).mock(return_value=httpx.Response(201))
    commit_route = respx_mock.put(commit_url).mock(return_value=httpx.Response(201))

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
        complete_url=commit_url,
        file_size=10,
        file_path=str(file_path),
    )

    assert response.status_code == 201
    assert commit_route.called
    body = commit_route.calls.last.request.content.decode()
    block_1 = AzureFileHandler._get_block_id(1)
    block_2 = AzureFileHandler._get_block_id(2)
    assert f"<Latest>{block_1}</Latest>" in body
    assert f"<Latest>{block_2}</Latest>" in body


@pytest.mark.respx
def test_upload_multipart_error_wrapped(
    tmp_path: Path, respx_mock: MockRouter
) -> None:
    file_path = tmp_path / "model.fnnx"
    file_path.write_bytes(b"01234")
    part_url = "https://blob.example.com/part1"
    respx_mock.put(part_url).mock(return_value=httpx.Response(403))
    parts = [
        PartDetails(part_number=1, url=part_url, start_byte=0, end_byte=4, part_size=5)
    ]
    handler = _handler()

    with pytest.raises(FileUploadError, match="Multipart upload failed"):
        handler.upload_multipart(
            parts=parts,
            complete_url="https://blob.example.com/commit",
            file_size=5,
            file_path=str(file_path),
        )


def test_upload_single_block_reads_correct_range(tmp_path: Path) -> None:
    with MockRouter(assert_all_called=False) as respx_mock:
        file_path = tmp_path / "model.fnnx"
        file_path.write_bytes(b"0123456789")
        part_url = "https://blob.example.com/part"
        route = respx_mock.put(part_url).mock(return_value=httpx.Response(201))
        part = PartDetails(
            part_number=4, url=part_url, start_byte=2, end_byte=5, part_size=4
        )
        updates: list[int] = []

        block_id = AzureFileHandler._upload_single_block(
            part, str(file_path), Lock(), updates.append
        )

        assert block_id == AzureFileHandler._get_block_id(4)
        assert updates == [4]
        assert route.calls.last.request.content == b"2345"
