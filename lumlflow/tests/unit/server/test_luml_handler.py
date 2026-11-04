import socket
from unittest.mock import patch

import pytest
from lumlflow.handlers.luml.luml import LumlHandler
from lumlflow.infra.exceptions import ApplicationError


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_unreachable_luml_reads_as_503_naming_the_address(monkeypatch) -> None:
    url = f"http://127.0.0.1:{_closed_port()}"
    monkeypatch.setattr("lumlflow.handlers.luml.base_luml.config.LUML_BASE_URL", url)
    handler = LumlHandler(tracker=object())  # type: ignore[arg-type]
    with patch.object(
        type(handler)._BaseLumlHandler__auth,  # type: ignore[attr-defined]
        "get_stored_credentials",
        return_value=type("Creds", (), {"api_key": "dfs_test"})(),
    ):
        with pytest.raises(ApplicationError) as failure:
            handler.get_luml_organizations()
    assert failure.value.status_code == 503
    assert url in failure.value.message
    assert "LUML_BASE_URL" in failure.value.message


def test_an_html_answer_reads_as_502_naming_the_address(monkeypatch) -> None:
    pass
    import httpx
    from luml_api._exceptions import InternalServerError

    url = "https://example.invalid"
    page = httpx.Response(
        200,
        text="<!doctype html>",
        request=httpx.Request("GET", f"{url}/v1/users/me/organizations"),
    )
    monkeypatch.setattr("lumlflow.handlers.luml.base_luml.config.LUML_BASE_URL", url)
    handler = LumlHandler(tracker=object())  # type: ignore[arg-type]
    with (
        patch.object(
            type(handler)._BaseLumlHandler__auth,  # type: ignore[attr-defined]
            "get_stored_credentials",
            return_value=type("Creds", (), {"api_key": "dfs_test"})(),
        ),
        patch(
            "lumlflow.handlers.luml.base_luml.LumlClient",
            side_effect=InternalServerError(
                "Failed to parse response", response=page, body=None
            ),
        ),
    ):
        with pytest.raises(ApplicationError) as failure:
            handler.get_luml_organizations()
    assert failure.value.status_code == 502
    assert url in failure.value.message
