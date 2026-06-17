from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from respx import MockRouter

from luml_api._exceptions import FileDownloadError
from luml_api._types import PartDetails
from luml_api.handlers.base_file_handler import BaseFileHandler
from luml_api.utils.progress import BaseProgressHandler


class _ConcreteFileHandler(BaseFileHandler):
    """Minimal concrete subclass to exercise the base class behaviour."""

    def upload_simple(
        self,
        url: str,
        file_path: str,
        file_size: int,
        file_name: str = "",
    ) -> httpx.Response:  # pragma: no cover - not used in tests
        raise NotImplementedError

    def upload_multipart(
        self,
        parts: list[PartDetails],
        complete_url: str,
        file_size: int,
        file_path: str,
        file_name: str = "",
        upload_id: str | None = None,
    ) -> httpx.Response:  # pragma: no cover - not used in tests
        raise NotImplementedError


@pytest.mark.parametrize(
    ("file_size", "expected_chunk"),
    [
        (0, 1048576),
        (10485759, 1048576),
        (10485760, 4194304),
        (52428800, 16777216),
        (104857600, 67108864),
        (524288000, 134217728),
        (1073741824, 268435456),
        (5368709120, 268435456),
        (10737418240, 268435456),
    ],
)
def test_calculate_optimal_chunk_size(file_size: int, expected_chunk: int) -> None:
    assert (
        _ConcreteFileHandler._calculate_optimal_chunk_size(file_size) == expected_chunk
    )


def test_create_progress_bar_uses_custom_handler() -> None:
    handler = _ConcreteFileHandler()
    progress = Mock(spec=BaseProgressHandler)
    handler.on_progress = progress

    update = handler.create_progress_bar(total_size=100, file_name="model.fnnx")

    progress.start.assert_called_once_with("model.fnnx", 100)
    assert update == progress.update


def test_create_progress_bar_defaults_to_print_handler() -> None:
    handler = _ConcreteFileHandler()

    update = handler.create_progress_bar(total_size=100, file_name="model.fnnx")

    assert callable(update)
    handler.finish_progress()


def test_finish_progress_without_active_handler_is_noop() -> None:
    handler = _ConcreteFileHandler()
    # Should not raise even though no progress bar was created.
    handler.finish_progress()


def test_finish_progress_calls_active_handler() -> None:
    handler = _ConcreteFileHandler()
    progress = Mock(spec=BaseProgressHandler)
    handler.on_progress = progress
    handler.create_progress_bar(total_size=10)

    handler.finish_progress()

    progress.finish.assert_called_once_with()


def test_create_file_generator_yields_chunks(tmp_path: Path) -> None:
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"abcdefghij")
    handler = _ConcreteFileHandler()
    updates: list[int] = []

    chunks = list(
        handler.create_file_generator(
            file_path=str(file_path),
            file_size=10,
            update_progress=updates.append,
            chunk_size=4,
        )
    )

    assert chunks == [b"abcd", b"efgh", b"ij"]
    assert updates == [4, 4, 2]


def test_create_file_generator_default_chunk_size(tmp_path: Path) -> None:
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"hello world")
    handler = _ConcreteFileHandler()
    updates: list[int] = []

    chunks = list(
        handler.create_file_generator(
            file_path=str(file_path),
            file_size=11,
            update_progress=updates.append,
        )
    )

    assert b"".join(chunks) == b"hello world"
    assert sum(updates) == 11


@pytest.mark.respx
def test_download_file_with_progress_success(
    tmp_path: Path, respx_mock: MockRouter
) -> None:
    url = "https://storage.example.com/download"
    content = b"x" * 2048
    respx_mock.get(url).mock(
        return_value=httpx.Response(
            200,
            content=content,
            headers={"content-length": str(len(content))},
        )
    )
    target = tmp_path / "out.bin"
    handler = _ConcreteFileHandler()
    handler.on_progress = Mock(spec=BaseProgressHandler)

    result = handler.download_file_with_progress(url, str(target), "out.bin")

    assert result == str(target)
    assert target.read_bytes() == content
    handler.on_progress.finish.assert_called_once_with()


@pytest.mark.respx
def test_download_file_with_progress_error(
    tmp_path: Path, respx_mock: MockRouter
) -> None:
    url = "https://storage.example.com/download"
    respx_mock.get(url).mock(return_value=httpx.Response(404))
    target = tmp_path / "out.bin"
    handler = _ConcreteFileHandler()
    handler.on_progress = Mock(spec=BaseProgressHandler)

    with pytest.raises(FileDownloadError):
        handler.download_file_with_progress(url, str(target), "out.bin")


def test_initiate_multipart_upload_base_returns_none() -> None:
    handler = _ConcreteFileHandler()
    assert handler.initiate_multipart_upload("https://example.com") is None
