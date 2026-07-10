"""AuthHandler.set_api_key error reporting.

Regression for the publish flow's "Could not reach LUML platform"
dead-end: the handler swallowed the underlying exception, so the TUI
could not tell a stale LUML_BASE_URL override from a proxy failure or
a malformed pasted key. The 502 must carry the target URL and cause.
"""

from typing import Any

import httpx
import pytest
from lumlflow.handlers.auth import AuthHandler
from lumlflow.infra.exceptions import ApplicationError
from lumlflow.schemas.auth import SetApiKey
from lumlflow.settings import get_config


class _RaisingClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __enter__(self) -> "_RaisingClient":
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def get(self, *args: Any, **kwargs: Any) -> httpx.Response:
        raise self._exc


class TestSetApiKeyUnreachable:
    def test_error_includes_url_and_cause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            httpx,
            "Client",
            lambda *a, **k: _RaisingClient(
                httpx.ConnectError("connection refused")
            ),
        )
        with pytest.raises(ApplicationError) as exc_info:
            AuthHandler().set_api_key(SetApiKey(api_key="luml_sk_test"))
        assert exc_info.value.status_code == 502
        message = exc_info.value.message
        assert get_config().LUML_BASE_URL in message
        assert "ConnectError" in message
        assert "connection refused" in message

    def test_non_network_exception_also_carries_cause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed key (e.g. invisible characters from a paste) makes
        httpx raise before any I/O — the message must still expose it."""

        monkeypatch.setattr(
            httpx,
            "Client",
            lambda *a, **k: _RaisingClient(
                httpx.LocalProtocolError("Illegal header value b'Bearer x\\n'")
            ),
        )
        with pytest.raises(ApplicationError) as exc_info:
            AuthHandler().set_api_key(SetApiKey(api_key="x\n"))
        assert exc_info.value.status_code == 502
        assert "LocalProtocolError" in exc_info.value.message
        assert "Illegal header value" in exc_info.value.message
