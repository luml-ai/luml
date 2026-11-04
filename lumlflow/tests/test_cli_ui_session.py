from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from lumlflow.cli import app
from lumlflow.server import app as server_app
from lumlflow.session import SESSION_TOKEN_FILE
from lumlflow.settings import get_config
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    store = tmp_path / "experiments"
    monkeypatch.setenv("BACKEND_STORE_URI", str(store))
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.delenv("LUMLFLOW_SESSION_TOKEN", raising=False)
    get_config.cache_clear()
    yield store
    get_config.cache_clear()


def _launch_token(*arguments: str) -> str:
    with patch("lumlflow.cli.uvicorn.run"):
        result = CliRunner().invoke(app, ["ui", "--no-browser", *arguments])
    assert result.exit_code == 0
    url = result.output.split("Lumlflow UI available at ", 1)[1].strip()
    return parse_qs(urlsplit(url).fragment)["session-token"][0]


def test_no_browser_launch_url_matches_the_running_session() -> None:
    with patch("lumlflow.cli.uvicorn.run") as run:
        result = CliRunner().invoke(app, ["ui", "--no-browser"])
    assert result.exit_code == 0
    url = result.output.split("Lumlflow UI available at ", 1)[1].strip()
    assert parse_qs(urlsplit(url).fragment)["session-token"] == [
        server_app.state.session_token
    ]
    assert run.call_args.args[0] is server_app


def test_automatic_browser_launch_uses_the_session_url() -> None:
    with (
        patch("lumlflow.cli.uvicorn.run"),
        patch("lumlflow.cli.time.sleep"),
        patch("lumlflow.cli.webbrowser.open") as browser,
        patch("lumlflow.cli.threading.Thread") as thread,
    ):
        result = CliRunner().invoke(app, ["ui"])
        thread.call_args.kwargs["target"]()
    assert result.exit_code == 0
    assert server_app.state.session_token not in result.output
    url = browser.call_args.args[0]
    assert parse_qs(urlsplit(url).fragment)["session-token"] == [
        server_app.state.session_token
    ]


def test_session_token_survives_a_restart(store: Path) -> None:
    first = _launch_token()
    assert _launch_token() == first
    token_file = store / SESSION_TOKEN_FILE
    assert token_file.read_text() == first
    assert token_file.stat().st_mode & 0o777 == 0o600


def test_rotate_token_issues_a_new_session_token(store: Path) -> None:
    first = _launch_token()
    rotated = _launch_token("--rotate-token")
    assert rotated != first
    assert server_app.state.session_token == rotated
    assert (store / SESSION_TOKEN_FILE).read_text() == rotated
    assert _launch_token() == rotated


def test_session_token_from_the_environment_is_not_stored(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LUMLFLOW_SESSION_TOKEN", "given-by-the-launcher")
    get_config.cache_clear()
    running = server_app.state.session_token
    assert _launch_token() == running
    assert not (store / SESSION_TOKEN_FILE).exists()
