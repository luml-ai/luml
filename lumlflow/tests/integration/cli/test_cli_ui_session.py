import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from lumlflow import __version__
from lumlflow.cli import app
from lumlflow.flow.daemon import client
from lumlflow.flow.daemon import main as server
from lumlflow.flow.daemon.workspace import STATE_DIR_ENV, DaemonRecord
from lumlflow.session import SESSION_TOKEN_FILE, session_token_for
from lumlflow.settings import get_config
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    store = (tmp_path / "experiments").resolve()
    monkeypatch.setenv("BACKEND_STORE_URI", str(store))
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.delenv("LUMLFLOW_SESSION_TOKEN", raising=False)
    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    monkeypatch.chdir(tmp_path)
    get_config.cache_clear()
    yield store
    get_config.cache_clear()


def _record(store: Path) -> DaemonRecord:
    return DaemonRecord(
        pid=1,
        instance_id="instance",
        port=1,
        token="daemon-token",
        web_host="127.0.0.1",
        web_port=2,
        tracker_store=str(store),
        version=__version__,
    )


@pytest.fixture
def serving(store: Path, monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    rotations: list[bool] = []

    def serve_here(
        root: Path, *, announce: Any, rotate_session_token: bool, **_: Any
    ) -> int:
        rotations.append(rotate_session_token)
        session_token_for(store, rotate_session_token)
        announce(_record(store))
        return 0

    monkeypatch.setattr(server, "serve_here", serve_here)
    monkeypatch.setattr(client, "discover", lambda: None)
    return rotations


def _launch_token(*arguments: str) -> str:
    result = CliRunner().invoke(app, ["ui", "--no-browser", *arguments])
    assert result.exit_code == 0, result.output
    url = next(word for word in result.output.split() if word.startswith("http://"))
    return parse_qs(urlsplit(url).fragment)["session-token"][0]


def test_launch_url_carries_the_stored_session_token(
    store: Path, serving: list[bool]
) -> None:
    token = _launch_token()
    token_file = store / SESSION_TOKEN_FILE
    assert token_file.read_text() == token
    if sys.platform != "win32":
        assert token_file.stat().st_mode & 0o777 == 0o600
    assert serving == [False]


def test_session_token_survives_a_restart(serving: list[bool]) -> None:
    assert _launch_token() == _launch_token()


def test_rotate_token_issues_a_new_session_token(
    store: Path, serving: list[bool]
) -> None:
    first = _launch_token()
    rotated = _launch_token("--rotate-token")
    assert rotated != first
    assert (store / SESSION_TOKEN_FILE).read_text() == rotated
    assert _launch_token() == rotated
    assert serving == [False, True, False]


def test_session_token_from_the_environment_is_not_stored(
    store: Path, serving: list[bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LUMLFLOW_SESSION_TOKEN", "given-by-the-launcher")
    get_config.cache_clear()
    assert _launch_token() == "given-by-the-launcher"
    assert not (store / SESSION_TOKEN_FILE).exists()


def test_attaching_opens_the_running_daemon_with_its_session_token(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = session_token_for(store)
    monkeypatch.setattr(client, "discover", lambda: _record(store))
    assert _launch_token() == running


def test_attaching_refuses_to_rotate_a_running_daemons_token(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = session_token_for(store)
    monkeypatch.setattr(client, "discover", lambda: _record(store))
    result = CliRunner().invoke(app, ["ui", "--no-browser", "--rotate-token"])
    assert result.exit_code == 1
    assert "lumlflow daemon stop" in result.output
    assert (store / SESSION_TOKEN_FILE).read_text() == running
