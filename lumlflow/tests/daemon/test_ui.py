"""`lumlflow ui`: a server the user starts, watches, and ends with Ctrl-C.

The signal handling, the port refusal and the second-instance handshake are
only true across processes, so those run the real command in its own process.
The rest — which port is asked for, what the help says, what is safe to
restart — is decided in-process and tested there.
"""

import json
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from lumlflow import cli as top_cli
from lumlflow.cli import app
from lumlflow.flow.daemon import client, web, workspace
from lumlflow.flow.daemon import main as server
from lumlflow.flow.daemon.workspace import DaemonRecord
from typer.main import get_command
from typer.testing import CliRunner

from tests.daemon.conftest import Reap
from tests.daemon.helpers import SCORE_CELL, make_workspace, write_cell

# A workspace root and the port asked for; hands back the running command.
Serve = Callable[..., "subprocess.Popen[str]"]

_READY_TIMEOUT_S = 90.0
_STOP_TIMEOUT_S = 90.0


@pytest.fixture
def serve(servers: Reap) -> Serve:
    """`lumlflow ui`, in its own process, ended when the test is."""

    def start(root: Path, *args: str) -> "subprocess.Popen[str]":
        running = subprocess.Popen(
            [sys.executable, "-m", "lumlflow.cli", "ui", "--no-browser", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        servers(running)
        return running

    return start


def test_the_default_port_is_5000_and_a_flag_is_what_changes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """5000 is the address the product has; asking for another is a gesture."""
    root = make_workspace(tmp_path / "project", flows=())
    asked: list[int] = []

    def note(root: Path, *, web_port: int, announce: Any) -> int:
        asked.append(web_port)
        return 0

    monkeypatch.setattr(server, "serve_here", note)
    monkeypatch.setattr(client, "live_record", lambda _: None)
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui", "--no-browser"])
    runner.invoke(app, ["ui", "--no-browser", "--port", "5173"])
    runner.invoke(app, ["ui", "--no-browser", "-p", "8080"])

    assert asked == [top_cli.DEFAULT_PORT, 5173, 8080]
    assert top_cli.DEFAULT_PORT == 5000


def test_the_browser_is_opened_on_the_address_that_carries_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tab is handed the key by being opened, or it is not connected at all.

    The flow API asks every caller for this workspace's token and the SPA is
    the one caller with no other way to have it, so what gets opened is the
    printed address in full — never the bare port.
    """
    root = make_workspace(tmp_path / "project", flows=())
    record = _record(foreground=True)
    opened = _opens(monkeypatch)

    def announcing(root: Path, *, web_port: int, announce: Any) -> int:
        announce(record)
        return 0

    monkeypatch.setattr(server, "serve_here", announcing)
    monkeypatch.setattr(client, "live_record", lambda _: None)
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui"])
    runner.invoke(app, ["ui", "--no-browser"])

    assert opened == [f"http://127.0.0.1:{record.web_port}/?token={record.token}"]


def test_a_second_ui_opens_the_browser_on_the_one_already_serving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Attaching is a way to reach the first, so it owes the same address —
    with the key the server that is actually serving minted, not a new one."""
    root = make_workspace(tmp_path / "project", flows=())
    record = _record(foreground=True)
    opened = _opens(monkeypatch)
    started: list[Path] = []

    monkeypatch.setattr(client, "live_record", lambda _: record)
    monkeypatch.setattr(client, "stand_down", lambda _: False)
    monkeypatch.setattr(server, "serve_here", lambda root, **_: started.append(root))
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui"])
    runner.invoke(app, ["ui", "--no-browser"])

    assert opened == [f"http://127.0.0.1:{record.web_port}/?token={record.token}"]
    # It attached; nothing was started to open a browser on.
    assert started == []


def test_the_web_app_is_looked_at_before_serving_and_before_attaching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both ways out of `ui` end with a browser on files built from a checkout,
    so both pass what checks them. What that check decides is tested apart."""
    root = make_workspace(tmp_path / "project", flows=())
    looked: list[Path] = []
    monkeypatch.setattr(top_cli, "_refresh_web_app", looked.append)
    monkeypatch.setattr(server, "serve_here", lambda root, **_: 0)
    monkeypatch.setattr(client, "live_record", lambda _: None)
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui", "--no-browser"])
    monkeypatch.setattr(client, "live_record", lambda _: _record(foreground=True))
    monkeypatch.setattr(client, "stand_down", lambda _: False)
    runner.invoke(app, ["ui", "--no-browser"])

    assert looked == [Path(top_cli.__file__).resolve().parent] * 2


def _opens(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """What `lumlflow ui` sent to a browser, in order."""
    opened: list[str] = []

    def open_url(url: str, *args: Any, **kwargs: Any) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(webbrowser, "open", open_url)
    return opened


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGINT to a child there")
def test_ctrl_c_ends_it_and_everything_it_was_holding(
    tmp_path: Path, serve: Serve
) -> None:
    """The whole point of the foreground: nothing it started survives it."""
    root = make_workspace(tmp_path / "project", flows=())
    port = _free_port()

    running = serve(root, "--port", str(port))
    record = _served(root, port)
    answered = _rpc(record)

    running.send_signal(signal.SIGINT)
    printed, _ = running.communicate(timeout=_STOP_TIMEOUT_S)

    assert answered["result"]["workspace"] == str(root)
    assert running.returncode == 0
    assert f"http://127.0.0.1:{port}/?token={record.token}" in printed
    assert "Ctrl+C" in printed
    assert "Traceback" not in printed
    # Deregistered, unlocked, and the port handed back: nothing left behind.
    assert workspace.read_record(root) is None
    lock = workspace.WorkspaceLock(root)
    assert lock.acquire()
    lock.release()
    _rebindable(port)


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGINT to a child there")
def test_ctrl_c_takes_the_kernels_it_spawned_with_it(
    tmp_path: Path, serve: Serve
) -> None:
    """Surviving nothing reaches past the server itself: a kernel left running
    would hold the workspace's env and its stores open with nobody driving."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    port = _free_port()

    running = serve(root, "--port", str(port))
    record = _served(root, port)
    ran = _rpc(record, "run", flow="churn", target="score")
    spawned = _kernels(root)

    running.send_signal(signal.SIGINT)
    running.communicate(timeout=_STOP_TIMEOUT_S)

    assert ran["result"]["executed"] == ["score"]
    assert running.returncode == 0
    assert spawned != []
    assert _settled(lambda: _kernels(root) == [])


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX signals there")
def test_a_terminating_signal_lets_go_the_same_way(
    tmp_path: Path, serve: Serve
) -> None:
    """A supervisor that stops it is the same gesture as a person doing so."""
    root = make_workspace(tmp_path / "project", flows=())
    port = _free_port()

    running = serve(root, "--port", str(port))
    _served(root, port)

    running.send_signal(signal.SIGTERM)
    running.communicate(timeout=_STOP_TIMEOUT_S)

    assert running.returncode == 0
    assert workspace.read_record(root) is None


def test_a_port_somebody_else_holds_is_a_refusal_that_names_it(
    tmp_path: Path, serve: Serve
) -> None:
    """Never a quiet move to another port: the address was the request."""
    root = make_workspace(tmp_path / "project", flows=())
    held = socket.socket()
    held.bind(("127.0.0.1", 0))
    held.listen(1)
    port = int(held.getsockname()[1])

    try:
        running = serve(root, "--port", str(port))
        printed, refused = running.communicate(timeout=_STOP_TIMEOUT_S)
    finally:
        held.close()

    assert running.returncode == 1
    assert f"port {port} is already in use" in refused
    assert "--port" in refused
    assert printed == ""
    # It refused before taking anything: no workspace was claimed on the way.
    assert workspace.read_record(root) is None


def test_a_second_ui_here_opens_the_one_already_serving(
    tmp_path: Path, serve: Serve
) -> None:
    """Two terminals, one workspace. The second is a way to reach the first,
    not a rival for the same stores — and it says which port answered."""
    root = make_workspace(tmp_path / "project", flows=())
    port, wanted = _free_port(), _free_port()

    serve(root, "--port", str(port))
    record = _served(root, port)
    second = subprocess.run(
        [sys.executable, "-m", "lumlflow.cli", "ui", "--no-browser", "-p", str(wanted)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=_STOP_TIMEOUT_S,
    )

    assert second.returncode == 0
    assert f"http://127.0.0.1:{port}/?token={record.token}" in second.stdout
    assert f"it is serving port {port}, not {wanted}" in second.stdout
    # The first is untouched, and no second server took the workspace.
    assert workspace.read_record(root) == record


def test_two_workspaces_serve_at_once_on_their_own_ports(
    tmp_path: Path, serve: Serve
) -> None:
    """The normal case: a project per terminal, each with its own `ui`."""
    roots = [make_workspace(tmp_path / name, flows=()) for name in ("one", "two")]
    ports = [_free_port(), _free_port()]

    for root, port in zip(roots, ports, strict=True):
        serve(root, "--port", str(port))
    records = [_served(root, port) for root, port in zip(roots, ports, strict=True)]

    assert [record.web_port for record in records] == ports
    assert [_rpc(record)["result"]["workspace"] for record in records] == [
        str(root) for root in roots
    ]


def test_a_verb_still_starts_a_server_behind_the_user(tmp_path: Path) -> None:
    """Plumbing stays plumbing: a verb that finds nobody home starts one, in
    the background, and says nothing about it."""
    root = make_workspace(tmp_path / "project", flows=())

    done = subprocess.run(
        [sys.executable, "-m", "lumlflow.cli", "status"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=_STOP_TIMEOUT_S,
    )
    record = workspace.read_record(root)

    assert done.returncode == 0
    assert "daemon" not in (done.stdout + done.stderr).lower()
    assert record is not None and not record.foreground
    assert client.is_alive(record)


def test_ui_takes_over_the_background_server_a_verb_left_behind(
    tmp_path: Path, serve: Serve
) -> None:
    """Idle plumbing is replaceable, and `ui` is what asks for the port."""
    root = make_workspace(tmp_path / "project", flows=())
    port = _free_port()
    with client.connect(root) as background:
        behind = background.record
        assert not behind.foreground

    serve(root, "--port", str(port))
    record = _served(root, port)

    assert record.foreground
    assert record.pid != behind.pid
    assert not client.is_alive(behind)


def test_a_server_carrying_a_run_keeps_the_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A port is never worth someone else's half-finished job."""
    asked: list[str] = []
    monkeypatch.setattr(client, "attach", _answering({"running": 1}, asked))

    assert client.stand_down(_record(foreground=False)) is False
    assert asked == ["ping"]


def test_a_server_a_person_is_watching_keeps_the_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restarting one would take a terminal somebody is looking at out from
    under them — so the second `ui` attaches to it instead."""
    asked: list[str] = []
    monkeypatch.setattr(client, "attach", _answering({"running": 0}, asked))

    assert client.stand_down(_record(foreground=True)) is False
    assert asked == []


def test_no_help_the_product_offers_says_daemon() -> None:
    """The background process is not a thing the user is asked to know about.

    The `daemon` group survives for tests and power users, hidden: it is not
    on any page the product hands out.
    """
    runner = CliRunner()
    root = runner.invoke(app, ["--help"])

    pages = {
        path: runner.invoke(app, [*path, "--help"]).output
        for path in _command_paths()
        if path[:1] != ("daemon",)
    }

    assert "daemon" not in root.output.lower()
    assert [path for path, text in pages.items() if "daemon" in text.lower()] == []
    # Hidden, not removed.
    assert ("daemon", "stop") in set(_command_paths())


def _command_paths() -> list[tuple[str, ...]]:
    """Every command the app can be asked for help on, group or leaf."""

    def walk(command: Any, path: tuple[str, ...]) -> list[tuple[str, ...]]:
        found = [path] if path else []
        for name, sub in getattr(command, "commands", {}).items():
            found += walk(sub, (*path, name))
        return found

    return walk(get_command(app), ())


def _record(*, foreground: bool) -> DaemonRecord:
    return DaemonRecord(
        workspace="/nowhere",
        pid=1,
        port=1,
        token="t",
        started="now",
        web_port=2,
        foreground=foreground,
    )


def _answering(payload: dict[str, Any], asked: list[str]) -> Any:
    """A stand-in connection: records what it was asked, answers one thing."""

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def call(self, method: str, params: Any = None) -> Any:
            asked.append(method)
            return payload

    return lambda record, **kwargs: Connection()


def _served(root: Path, port: int) -> DaemonRecord:
    """The record of a `ui` that has come up, or the reason it never did."""
    deadline = time.monotonic() + _READY_TIMEOUT_S
    while time.monotonic() < deadline:
        record = workspace.read_record(root)
        if record is not None and record.web_port == port and client.is_alive(record):
            return record
        time.sleep(0.05)
    raise AssertionError(f"nothing came up on port {port} for {root}")


def _rpc(record: DaemonRecord, method: str = "status", **params: Any) -> Any:
    answered = httpx.post(
        f"http://127.0.0.1:{record.web_port}{web.RPC_PATH}",
        json={"method": method, "params": params},
        headers={web.TOKEN_HEADER: record.token},
        timeout=300.0,
    )
    return json.loads(answered.text)


def _kernels(root: Path) -> list[str]:
    """Kernel processes still running for this workspace, by command line."""
    listed = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True)
    return [
        line
        for line in listed.stdout.splitlines()
        if "lumlflow_kernel" in line and str(root) in line
    ]


def _settled(wanted: Callable[[], bool], timeout: float = 30.0) -> bool:
    """An OS reaps on its own schedule; the answer is what it settles on."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if wanted():
            return True
        time.sleep(0.1)
    return False


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _rebindable(port: int) -> None:
    with socket.socket() as after:
        after.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        after.bind(("127.0.0.1", port))
