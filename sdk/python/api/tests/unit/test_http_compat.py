import importlib
import subprocess
import sys
from pathlib import Path
from threading import Lock

import httpx2
import pytest

from luml_api import APIConnectionError
from luml_api._base_client import AsyncBaseClient, SyncBaseClient
from luml_api._types import PartDetails
from luml_api.handlers.azure_file_handler import AzureFileHandler
from luml_api.handlers.s3_file_handler import S3FileHandler


@pytest.mark.parametrize(
    "error_name", ["ConnectError", "ReadTimeout", "RemoteProtocolError"]
)
def test_sync_errors_preserve_legacy_catches(error_name: str) -> None:
    legacy = importlib.import_module("httpx")
    original = getattr(httpx2, error_name)("unavailable")

    def fail(request: httpx2.Request) -> httpx2.Response:
        raise original

    with SyncBaseClient("https://example.com") as client:
        client._client = httpx2.Client(transport=httpx2.MockTransport(fail))
        with pytest.raises(getattr(legacy, error_name)) as error:
            client.get("https://example.com")

    assert isinstance(error.value, httpx2.HTTPError)
    assert isinstance(error.value, legacy.HTTPError)
    assert isinstance(error.value, APIConnectionError)
    assert str(error.value) == "unavailable"


@pytest.mark.asyncio
async def test_async_errors_preserve_old_sdk_catch() -> None:
    legacy = importlib.import_module("httpx")

    def fail(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("unavailable", request=request)

    async with AsyncBaseClient("https://example.com") as client:
        client._client = httpx2.AsyncClient(transport=httpx2.MockTransport(fail))
        with pytest.raises(legacy.HTTPError) as error:
            await client.get("https://example.com")
    assert isinstance(error.value, APIConnectionError)
    assert error.value.request.url.host == "example.com"


@pytest.mark.parametrize("handler", [S3FileHandler, AzureFileHandler])
@pytest.mark.parametrize("transport_failure", [False, True])
def test_file_part_errors_preserve_legacy_catches(
    handler: type[S3FileHandler] | type[AzureFileHandler],
    transport_failure: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = importlib.import_module("httpx")
    path = tmp_path / "part"
    path.write_bytes(b"data")

    def answer(request: httpx2.Request) -> httpx2.Response:
        if transport_failure:
            raise httpx2.ConnectError("unavailable", request=request)
        return httpx2.Response(404, json={"detail": "missing"})

    factory = httpx2.Client
    monkeypatch.setattr(
        httpx2,
        "Client",
        lambda **kwargs: factory(transport=httpx2.MockTransport(answer), **kwargs),
    )
    part = PartDetails(
        part_number=1, part_size=4, start_byte=0, end_byte=3, url="https://example.com"
    )
    upload = (
        handler._upload_single_part
        if handler is S3FileHandler
        else handler._upload_single_block
    )
    expected = legacy.ConnectError if transport_failure else legacy.HTTPStatusError
    with pytest.raises(expected) as error:
        upload(part, str(path), Lock(), lambda _: None)
    assert isinstance(error.value, httpx2.HTTPError)
    if not transport_failure:
        assert error.value.response.status_code == 404
        assert error.value.response.json() == {"detail": "missing"}


def test_sdk_works_without_legacy_httpx() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys

class NoLegacyHTTPX(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "httpx" or fullname.startswith("httpx."):
            raise ModuleNotFoundError("httpx is not installed", name="httpx")

sys.meta_path.insert(0, NoLegacyHTTPX())
import httpx2
from luml_api import APIConnectionError
from luml_api._base_client import SyncBaseClient

def fail(request):
    raise httpx2.ConnectError("unavailable", request=request)

with SyncBaseClient("https://example.com") as client:
    client._client = httpx2.Client(transport=httpx2.MockTransport(fail))
    try:
        client.get("https://example.com")
    except APIConnectionError as error:
        assert isinstance(error, httpx2.ConnectError)
    else:
        raise AssertionError("expected an error")
assert "httpx" not in sys.modules
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
