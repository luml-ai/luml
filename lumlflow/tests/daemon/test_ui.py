"""`lumlflow ui`: a server the user starts, watches, and ends with Ctrl-C.

The signal handling, the port refusal and the second-instance handshake are
only true across processes, so those run the real command in its own process.
The rest — which port is asked for, what the help says, what is safe to
restart — is decided in-process and tested there.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import pytest
import websockets.sync.client
from lumlflow import __version__
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

_GATED_CELL = """
class Gated:
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        import time

        while not (ctx.workspace_dir / "go").exists():
            time.sleep(0.05)
        return {"summary": {"auc": 0.91}}
"""


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
    asked: list[tuple[str, int]] = []

    def note(root: Path, *, web_host: str, web_port: int, announce: Any) -> int:
        asked.append((web_host, web_port))
        return 0

    monkeypatch.setattr(server, "serve_here", note)
    monkeypatch.setattr(client, "discover", lambda: None)
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui", "--no-browser"])
    runner.invoke(app, ["ui", "--no-browser", "--port", "5173"])
    runner.invoke(app, ["ui", "--no-browser", "-p", "8080"])

    assert asked == [
        (top_cli.DEFAULT_HOST, top_cli.DEFAULT_PORT),
        (top_cli.DEFAULT_HOST, 5173),
        (top_cli.DEFAULT_HOST, 8080),
    ]
    assert top_cli.DEFAULT_HOST == "127.0.0.1"
    assert top_cli.DEFAULT_PORT == 5000


def test_ui_accepts_a_launch_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    elsewhere = make_workspace(tmp_path / "elsewhere", flows=())
    started: list[Path] = []

    def start(directory: Path, **_: Any) -> int:
        started.append(directory)
        return 0

    monkeypatch.setattr(client, "discover", lambda: None)
    monkeypatch.setattr(server, "serve_here", start)
    monkeypatch.chdir(elsewhere)

    result = CliRunner().invoke(app, ["ui", str(root), "--no-browser"])

    assert result.exit_code == 0, result.output
    assert started == [root.resolve()]


def test_the_browser_is_opened_on_the_address_that_carries_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tab is handed the key by being opened, or it is not connected at all.

    The flow API asks every caller for this workspace's token and the SPA is
    the one caller with no other way to have it, so what gets opened is the
    printed address in full — never the bare port.
    """
    root = make_workspace(tmp_path / "project", flows=())
    record = _record()
    opened = _opens(monkeypatch)

    def announcing(root: Path, *, web_host: str, web_port: int, announce: Any) -> int:
        announce(record)
        return 0

    monkeypatch.setattr(server, "serve_here", announcing)
    monkeypatch.setattr(client, "discover", lambda: None)
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui"])
    runner.invoke(app, ["ui", "--no-browser"])

    assert opened == [_ui_url(record, root)]


@pytest.mark.parametrize(
    ("host", "warned"),
    [("127.0.0.1", False), ("localhost", False), ("0.0.0.0", True)],
)
def test_ui_warns_only_for_a_non_loopback_bind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host: str,
    warned: bool,
) -> None:
    root = make_workspace(tmp_path / "project", flows=())

    def announcing(root: Path, *, web_host: str, web_port: int, announce: Any) -> int:
        announce(
            DaemonRecord(
                pid=1,
                instance_id="instance",
                port=1,
                token="t",
                web_host=web_host,
                web_port=web_port,
                tracker_store="/tmp/experiments",
                version=__version__,
            )
        )
        return 0

    monkeypatch.setattr(server, "serve_here", announcing)
    monkeypatch.setattr(client, "discover", lambda: None)
    monkeypatch.chdir(root)

    result = CliRunner().invoke(
        app, ["ui", "--no-browser", "--host", host, "--port", "7777"]
    )

    assert result.exit_code == 0, result.output
    assert (top_cli.NON_LOOPBACK_WARNING in result.output) is warned


def test_ui_warns_but_starts_on_a_network_state_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    started: list[Path] = []

    def start(directory: Path, **_: Any) -> int:
        started.append(directory)
        return 0

    monkeypatch.setattr(client, "discover", lambda: None)
    monkeypatch.setattr(workspace, "state_dir_is_local", lambda _: False)
    monkeypatch.setattr(server, "serve_here", start)
    monkeypatch.chdir(root)

    result = CliRunner().invoke(app, ["ui", "--no-browser"])

    assert result.exit_code == 0
    assert str(workspace.state_dir()) in result.output
    assert "file locks are unreliable" in result.output
    assert started == [root]


def test_a_non_loopback_host_is_bound_recorded_and_still_requires_the_token(
    tmp_path: Path, serve: Serve
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    port = _free_port()

    running = serve(root, "--host", "0.0.0.0", "--port", str(port))
    record = _served(root, port)
    unauthorized = httpx.post(
        f"http://127.0.0.1:{port}{web.RPC_PATH}",
        json={"method": "status", "params": {}},
        timeout=30.0,
    )
    authorized = _rpc(record)
    assert client.stop(record, timeout=_STOP_TIMEOUT_S)
    printed, errors = running.communicate(timeout=_STOP_TIMEOUT_S)

    assert record.web_host == "0.0.0.0"
    assert unauthorized.status_code == web.UNAUTHORIZED
    assert authorized["result"]["workspace"] == str(root)
    assert _ui_url(record, root) in printed
    assert f"daemon log: {workspace.log_path()}" in printed
    assert top_cli.NON_LOOPBACK_WARNING in printed
    assert errors == ""


def test_the_web_listener_binds_the_requested_non_loopback_host() -> None:
    listener = server._bind_exactly("0.0.0.0", 0)
    try:
        assert listener.getsockname()[0] == "0.0.0.0"
    finally:
        listener.close()


def test_a_second_ui_opens_the_browser_on_the_one_already_serving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Attaching is a way to reach the first, so it owes the same address —
    with the key the server that is actually serving minted, not a new one."""
    root = make_workspace(tmp_path / "project", flows=())
    record = _record()
    opened = _opens(monkeypatch)
    started: list[Path] = []

    monkeypatch.setattr(client, "discover", lambda: record)
    monkeypatch.setattr(server, "serve_here", lambda root, **_: started.append(root))
    monkeypatch.chdir(root)
    runner = CliRunner()

    runner.invoke(app, ["ui"])
    runner.invoke(app, ["ui", "--no-browser"])

    assert opened == [_ui_url(record, root)]
    # It attached; nothing was started to open a browser on.
    assert started == []


@pytest.mark.parametrize("explicit_path", [True, False])
def test_ui_refuses_a_store_that_differs_from_the_running_daemon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    explicit_path: bool,
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    running_store = (tmp_path / "running-store").resolve()
    requested_store = (tmp_path / "requested-store").resolve()
    record = _record(tracker_store=str(running_store))
    if explicit_path:
        monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(running_store))
        monkeypatch.setenv("BACKEND_STORE_URI", str(running_store))
    else:
        monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
        monkeypatch.setenv("BACKEND_STORE_URI", str(requested_store))
    monkeypatch.setattr(client, "discover", lambda: record)
    monkeypatch.chdir(root)
    args = ["ui", "--no-browser"]
    if explicit_path:
        args.extend(["--path", str(requested_store)])

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 1
    assert str(running_store) in result.output
    assert record.web_host in result.output
    assert "lumlflow daemon stop" in result.output
    if explicit_path:
        assert os.environ["LUML_BACKEND_STORE_URI"] == str(running_store)


def test_ui_refuses_a_host_that_differs_from_the_running_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    running_store = (tmp_path / "running-store").resolve()
    record = _record(tracker_store=str(running_store))
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.setenv("BACKEND_STORE_URI", str(running_store))
    monkeypatch.setattr(client, "discover", lambda: record)
    monkeypatch.chdir(root)

    result = CliRunner().invoke(
        app,
        ["ui", "--no-browser", "--host", "0.0.0.0"],
    )

    assert result.exit_code == 1
    assert str(running_store) in result.output
    assert record.web_host in result.output
    assert "lumlflow daemon stop" in result.output


def test_ui_attaches_without_interrupting_a_run_or_leased_session(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "gated", _GATED_CELL)

    with (
        ThreadPoolExecutor(max_workers=1) as executor,
        client.connect(root) as live,
        client.attach(live.record) as paired,
    ):
        live.call("flow.open", {"flow": "churn"})
        begun = paired.call(
            "agent.begin",
            {"flow": "churn", "actor": "codex", "label": "Codex", "lease": True},
        )
        runner = client.attach(live.record)
        running = executor.submit(
            runner.call, "run", {"flow": "churn", "target": "gated"}
        )
        try:
            assert _settled(lambda: _running(live.record) == 1)
            attached = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "lumlflow.cli",
                    "ui",
                    "--no-browser",
                ],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=_STOP_TIMEOUT_S,
            )
            status = paired.call("status", {"flow": "churn"})

            assert attached.returncode == 0, attached.stderr
            assert _ui_url(live.record, tmp_path) in attached.stdout
            assert not running.done()
            assert begun["leased"] is True
            assert status["flows"][0]["agent"] == "Codex"
            assert workspace.read_record() == live.record
        finally:
            (root / "go").touch()
            outcome = running.result(timeout=_STOP_TIMEOUT_S)
            runner.close()

    assert outcome["executed"] == ["gated"]


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
    assert _ui_url(record, root) in printed
    assert "Ctrl+C" in printed
    assert "Traceback" not in printed
    # Deregistered, unlocked, and the port handed back: nothing left behind.
    assert workspace.read_record() is None
    lock = workspace.WorkspaceLock()
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


@pytest.mark.skipif(sys.platform == "win32", reason="no SIGINT to a child there")
def test_ctrl_c_names_attached_clients_and_still_stops(
    tmp_path: Path, serve: Serve
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    other = make_workspace(tmp_path / "other")
    outside_flow = other / "churn.flow"
    port = _free_port()

    running = serve(root, "--port", str(port))
    record = _served(root, port)
    paired = client.attach(record)
    try:
        with websockets.sync.client.connect(
            f"ws://127.0.0.1:{port}{web.STREAM_PATH}?token={record.token}",
            open_timeout=30,
        ) as stream:
            paired.call("flow.open", {"flow": str(outside_flow), "worktree": False})
            paired.call(
                "agent.begin",
                {
                    "flow": str(outside_flow),
                    "actor": "codex",
                    "label": "Codex",
                    "lease": True,
                },
            )
            stream.send(json.dumps({"subscribe": "journal", "flow": str(outside_flow)}))
            _receive_catch_up(stream)

            running.send_signal(signal.SIGINT)
            printed, errors = running.communicate(timeout=_STOP_TIMEOUT_S)
    finally:
        paired.close()

    assert running.returncode == 0
    assert "attached clients" in printed
    assert "Codex" in printed
    assert "stream subscriber" in printed
    assert str(outside_flow) in printed
    assert errors == ""
    assert workspace.read_record() is None
    lock = workspace.WorkspaceLock()
    assert lock.acquire()
    lock.release()


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
    assert workspace.read_record() is None


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
    assert workspace.read_record() is None


def test_a_second_ui_in_another_directory_opens_the_one_already_serving(
    tmp_path: Path, serve: Serve
) -> None:
    """The launch directory does not select a second daemon."""
    root = make_workspace(tmp_path / "project", flows=())
    other = make_workspace(tmp_path / "other", flows=())
    port, wanted = _free_port(), _free_port()

    serve(root, "--port", str(port))
    record = _served(root, port)
    second = subprocess.run(
        [sys.executable, "-m", "lumlflow.cli", "ui", "--no-browser", "-p", str(wanted)],
        cwd=other,
        capture_output=True,
        text=True,
        timeout=_STOP_TIMEOUT_S,
    )

    assert second.returncode == 0
    assert _ui_url(record, other) in second.stdout
    assert f"it is serving port {port}, not {wanted}" in second.stdout
    # The first is untouched, and no second server took the workspace.
    assert workspace.read_record() == record


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
    record = workspace.read_record()

    assert done.returncode == 0
    assert "daemon" not in (done.stdout + done.stderr).lower()
    assert record is not None
    assert record.web_host == top_cli.DEFAULT_HOST
    assert record.web_port == top_cli.DEFAULT_PORT
    assert client.is_alive(record)


def test_a_background_daemon_uses_an_ephemeral_port_when_5000_is_taken(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    held = socket.socket()
    try:
        held.bind((top_cli.DEFAULT_HOST, top_cli.DEFAULT_PORT))
    except OSError:
        held.close()
        pytest.skip("port 5000 is already occupied outside this test")
    held.listen(1)
    try:
        done = subprocess.run(
            [sys.executable, "-m", "lumlflow.cli", "status"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=_STOP_TIMEOUT_S,
        )
    finally:
        held.close()

    record = workspace.read_record()
    assert done.returncode == 0
    assert record is not None and record.web_port > 0
    assert record.web_port != top_cli.DEFAULT_PORT


def test_a_background_daemon_records_the_store_from_its_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    tracker_store = tmp_path / "tracker"
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.setenv("BACKEND_STORE_URI", str(tracker_store))

    done = subprocess.run(
        [sys.executable, "-m", "lumlflow.cli", "status"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=_STOP_TIMEOUT_S,
    )

    record = workspace.read_record()
    assert done.returncode == 0
    assert record is not None
    assert record.tracker_store == str(tracker_store.resolve())


def test_daemon_stop_and_status_are_visible_but_start_is_hidden() -> None:
    runner = CliRunner()
    root = runner.invoke(app, ["--help"])
    daemon = runner.invoke(app, ["daemon", "--help"])
    commands = set(_command_paths())

    assert "daemon" in root.output
    assert "status" in daemon.output and "stop" in daemon.output
    assert "start" not in daemon.output
    assert {("daemon", "start"), ("daemon", "status"), ("daemon", "stop")} <= commands
    assert ("root",) not in commands
    assert "--workspace" not in runner.invoke(app, ["mcp", "--help"]).output
    module = subprocess.run(
        [sys.executable, "-m", "lumlflow.flow.daemon", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert module.returncode == 0
    assert "--workspace" not in module.stdout


def _command_paths() -> list[tuple[str, ...]]:
    """Every command the app can be asked for help on, group or leaf."""

    def walk(command: Any, path: tuple[str, ...]) -> list[tuple[str, ...]]:
        found = [path] if path else []
        for name, sub in getattr(command, "commands", {}).items():
            found += walk(sub, (*path, name))
        return found

    return walk(get_command(app), ())


def _record(*, tracker_store: str | None = None) -> DaemonRecord:
    if tracker_store is None:
        from lumlflow.settings import Settings

        tracker_store = Settings().BACKEND_STORE_URI  # type: ignore[call-arg]
    return DaemonRecord(
        pid=1,
        instance_id="instance",
        port=1,
        token="t",
        web_host="127.0.0.1",
        web_port=2,
        tracker_store=tracker_store,
        version=__version__,
    )


def _ui_url(record: DaemonRecord, directory: Path) -> str:
    query = urlencode(
        {
            "token": record.token,
            "directory": str(directory.resolve()),
            "log": str(workspace.log_path()),
        }
    )
    return f"http://{record.web_host}:{record.web_port}/flow?{query}"


def _served(root: Path, port: int) -> DaemonRecord:
    """The record of a `ui` that has come up, or the reason it never did."""
    deadline = time.monotonic() + _READY_TIMEOUT_S
    while time.monotonic() < deadline:
        record = workspace.read_record()
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


def _running(record: DaemonRecord) -> int:
    with client.attach(record, timeout=5) as probe:
        return int(probe.call("ping")["running"])


def _receive_catch_up(
    stream: "websockets.sync.client.ClientConnection",
) -> None:
    while True:
        frame = json.loads(stream.recv(timeout=30))
        if frame["type"] == "caught_up":
            return


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _rebindable(port: int) -> None:
    with socket.socket() as after:
        after.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        after.bind(("127.0.0.1", port))
