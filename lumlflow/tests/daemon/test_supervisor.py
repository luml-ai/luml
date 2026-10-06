"""The supervisor: one daemon per workspace, started by whoever needs it.

These run the real thing — `python -m lumlflow.flow.daemon` in its own process,
reached over its loopback socket — because the singleton, the discovery record
and the restart are only true if they are true across processes.
"""

import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
import pytest
import websockets.exceptions
import websockets.sync.client
from lumlflow import __version__
from lumlflow.cli import app
from lumlflow.flow.daemon import client, harnesses, web, workspace
from lumlflow.flow.daemon.main import ALREADY_RUNNING, INVALID_REQUEST, _activity
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowError, FlowNotFound, ServerError
from typer.testing import CliRunner

from tests.daemon.conftest import Reap
from tests.daemon.helpers import SCORE_CELL, make_workspace, write_cell

Starter = Callable[[Path], client.DaemonClient]
# Windows has no SIGKILL; there, terminating is already the hard kind.
HARD_KILL = getattr(signal, "SIGKILL", signal.SIGTERM)
_FRAME_LIMIT = 200

GATED_CELL = """
class Gated:
    \"\"\"Keeps going, and keeps saying so, until the workspace lets it stop.\"\"\"
    produces = {"summary": "asset"}

    def materialize(self, ctx):
        import time

        while not (ctx.workspace_dir / "go").exists():
            print("epoch 1 done")
            time.sleep(0.05)
        return {"summary": {"auc": 0.91}}
"""


@pytest.fixture
def start() -> Iterator[Starter]:
    """Start daemons, and make sure none outlives the test that started it.

    The client's own record is what gets killed, not whatever the discovery
    file says at teardown: a test that removes the record — which is the point
    of a couple of them — would otherwise leave its daemon running forever.
    """
    started: list[client.DaemonClient] = []

    def starter(root: Path) -> client.DaemonClient:
        live = client.connect(root)
        started.append(live)
        return live

    yield starter
    for live in started:
        _kill(live.record)


def _kill(record: DaemonRecord | None) -> None:
    if record is None:
        return
    with contextlib.suppress(Exception):
        with client.attach(record, timeout=5) as live:
            live.call("shutdown")
    with contextlib.suppress(OSError, ProcessLookupError):
        os.kill(record.pid, HARD_KILL)


def _caught_up(
    socket: "websockets.sync.client.ClientConnection",
) -> list[dict[str, Any]]:
    """The journal frames a subscribe answers with, up to the catch-up marker."""
    replayed: list[dict[str, Any]] = []
    while True:
        frame = json.loads(socket.recv(timeout=30))
        if frame["type"] == "caught_up":
            return replayed
        replayed.append(frame)


def _watch(
    record: DaemonRecord, flow: str
) -> "websockets.sync.client.ClientConnection":
    """A browser on this workspace, subscribed to one flow's journal."""
    stream = f"ws://127.0.0.1:{record.web_port}{web.STREAM_PATH}?token={record.token}"
    socket = websockets.sync.client.connect(stream, open_timeout=30)
    socket.send(json.dumps({"subscribe": "journal", "flow": flow}))
    return socket


def _until(
    socket: "websockets.sync.client.ClientConnection",
    wanted: Callable[[dict[str, Any]], bool],
) -> dict[str, Any]:
    for _ in range(_FRAME_LIMIT):
        frame = json.loads(socket.recv(timeout=30))
        if wanted(frame):
            return frame
    raise AssertionError("no frame matched")


def _wait_until_gone(record: DaemonRecord, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not client.is_alive(record):
            return
        time.sleep(0.05)
    raise AssertionError("the daemon is still answering")


def _wait_until_deregistered(root: Path, timeout: float = 30.0) -> None:
    """Answering stops first; the record is surrendered last, with the lock.

    Shutting down means closing kernels and stores, which takes as long as it
    takes — so the record outlives the socket on purpose: while it is there,
    the daemon it names still owns the workspace.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if workspace.read_record() is None:
            return
        time.sleep(0.05)
    raise AssertionError("the daemon is still registered")


def test_a_verb_that_finds_no_daemon_starts_one(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        status = live.call("status")

        record = workspace.read_record()
        assert record is not None
        assert record.port > 0 and record.token
        assert record.instance_id
        assert record.web_host == "127.0.0.1" and record.web_port > 0
        assert record.tracker_store and record.version == __version__
        assert status["workspace"] == str(root)
        assert status["pid"] == record.pid
        assert live.call("ping")["instance_id"] == record.instance_id
        assert [flow["flow"] for flow in status["flows"]] == ["churn"]


def test_the_daemon_serves_the_workbench_on_the_port_it_recorded(
    tmp_path: Path, start: Starter
):
    """The browser reaches a workspace the way every other verb does: through
    the record. Nothing here is in-process — this is uvicorn inside the daemon,
    a real socket upgrade, and the token standing between the two.
    """
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        record = workspace.read_record()
        assert record is not None and record.web_port > 0
        assert live.call("ping")["web"] == f"http://127.0.0.1:{record.web_port}"

        base = f"127.0.0.1:{record.web_port}"
        answered = httpx.post(
            f"http://{base}{web.RPC_PATH}",
            json={"method": "status"},
            headers={web.TOKEN_HEADER: record.token},
            timeout=30.0,
        )
        refused = httpx.post(
            f"http://{base}{web.RPC_PATH}", json={"method": "status"}, timeout=30.0
        )
        stream = f"ws://{base}{web.STREAM_PATH}?token={record.token}"
        with websockets.sync.client.connect(stream, open_timeout=30) as socket:
            socket.send(json.dumps({"subscribe": "journal", "flow": "churn"}))
            frames = _caught_up(socket)

        # Over a real upgrade, not the test transport: "you may not" has to
        # reach the client as its own close code rather than as the abnormal
        # closure a dropped socket produces.
        forged = f"ws://{base}{web.STREAM_PATH}?token=guess"
        with websockets.sync.client.connect(forged, open_timeout=30) as refused_socket:
            with pytest.raises(websockets.exceptions.ConnectionClosed) as closed:
                refused_socket.recv(timeout=30)

    assert answered.json()["result"]["workspace"] == str(root)
    assert refused.status_code == 401
    assert closed.value.rcvd is not None
    assert closed.value.rcvd.code == web.WS_UNAUTHORIZED
    assert frames[0]["transaction"]["intent"] == "created flow churn"
    assert [frame["step"] for frame in frames] == list(range(1, len(frames) + 1))


def test_a_tab_opened_mid_run_is_told_which_console_it_can_still_ask_for(
    tmp_path: Path, start: Starter
):
    """The ring holds a live run's tail; the catch-up is what makes it
    addressable. A run's lifecycle is never journaled, so a client that was not
    connected when the run started has no cursor that would reach it — and the
    console on the card it opens would stay empty for the ten minutes it has
    left to wait.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "gated", GATED_CELL)

    with start(root) as live:
        record = live.record
        live.call("flow.open", {"flow": "churn"})
        with ThreadPoolExecutor(max_workers=1) as pool, client.attach(record) as runner:
            with _watch(record, "churn") as early:
                _caught_up(early)
                running = pool.submit(
                    runner.call, "run", {"flow": "churn", "target": "gated"}
                )
                try:
                    # In flight from here — which is what makes the next
                    # connection a late one.
                    started = _until(
                        early, lambda frame: frame.get("event") == "started"
                    )
                    with _watch(record, "churn") as late:
                        marker = _until(
                            late, lambda frame: frame.get("type") == "caught_up"
                        )
                        in_flight = marker["running"][0]
                        late.send(
                            json.dumps(
                                {
                                    "subscribe": "logs",
                                    "flow": "churn",
                                    "run_id": in_flight["run_id"],
                                }
                            )
                        )
                        chunk = _until(
                            late, lambda frame: frame.get("channel") == "logs"
                        )
                finally:
                    (root / "go").write_text("", encoding="utf-8")
                outcome = running.result(timeout=120)

        # And once it is over, it is no longer offered as something to watch.
        with _watch(record, "churn") as after:
            ended = _until(after, lambda frame: frame.get("type") == "caught_up")

    # One branch asked for it, so one branch is waiting on it — the count a stop
    # gesture words itself from.
    assert in_flight == {"run_id": started["run_id"], "slug": "gated", "awaiting": 1}
    assert "epoch 1 done" in chunk["text"]
    assert outcome["executed"] == ["gated"]
    assert ended["running"] == []


def test_shutdown_lets_go_of_the_workspace_with_a_browser_still_watching(
    tmp_path: Path, start: Starter
):
    """A watching tab never closes on its own. A daemon that waited for one to
    would be a daemon nobody can stop while anybody is looking at it."""
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        record = live.record
        stream = (
            f"ws://127.0.0.1:{record.web_port}{web.STREAM_PATH}?token={record.token}"
        )
        with websockets.sync.client.connect(stream, open_timeout=30) as socket:
            socket.send(json.dumps({"subscribe": "journal", "flow": "churn"}))
            _caught_up(socket)

            live.call("shutdown")
            _wait_until_deregistered(root)


def test_two_verbs_starting_at_once_end_up_at_the_same_daemon(tmp_path: Path):
    """Both spawn; one loses the workspace and steps aside within milliseconds.
    The verb that started the loser still needs a daemon to talk to."""
    root = make_workspace(tmp_path / "project")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            racing = [pool.submit(client.start_daemon, root) for _ in range(2)]
            records = [attempt.result(timeout=60) for attempt in racing]

        assert records[0] == records[1]
        assert client.is_alive(records[0])
    finally:
        _kill(workspace.read_record())


def test_a_verb_waits_out_a_workspace_that_is_briefly_held(tmp_path: Path):
    """A daemon that finds the workspace taken exits at once. The verb that
    started it still needs a daemon, so it tries again rather than failing."""
    root = make_workspace(tmp_path / "project")
    lock = workspace.WorkspaceLock()
    assert lock.acquire()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            starting = pool.submit(client.start_daemon, root)
            time.sleep(1.0)
            lock.release()
            record = starting.result(timeout=60)

        assert client.is_alive(record)
    finally:
        lock.release()
        _kill(workspace.read_record())


def test_a_held_lock_that_does_not_answer_names_the_log_and_stop(
    tmp_path: Path, servers: Reap
) -> None:
    root = make_workspace(tmp_path / "project")
    script = "\n".join(
        [
            "import os, time",
            "from lumlflow import __version__",
            "from lumlflow.flow.daemon import workspace",
            "from lumlflow.flow.daemon.workspace import DaemonRecord",
            "lock = workspace.WorkspaceLock()",
            "assert lock.acquire()",
            "workspace.write_record(DaemonRecord(",
            "    pid=os.getpid(), instance_id='hung', port=9, token='t',",
            "    web_host='127.0.0.1', web_port=5000,",
            "    tracker_store='/tmp/experiments', version=__version__,",
            "))",
            "print('ready', flush=True)",
            "time.sleep(60)",
        ]
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    servers(holder)
    assert holder.stdout is not None and holder.stdout.readline().strip() == "ready"

    with pytest.raises(ServerError) as refused:
        client.connect(root)

    assert str(workspace.log_path()) in str(refused.value)
    assert "lumlflow daemon stop" in str(refused.value)
    assert holder.poll() is None
    assert workspace.read_record() is not None

    stopped = CliRunner().invoke(app, ["daemon", "stop"])
    assert stopped.exit_code == 0, stopped.output
    assert "daemon stopped" in stopped.output


def test_a_second_verb_reuses_the_daemon_that_is_already_there(
    tmp_path: Path, start: Starter
):
    root = make_workspace(tmp_path / "project")
    other = make_workspace(tmp_path / "other", flows=("sales",))

    with start(root) as first, client.connect(other) as second:
        assert first.call("ping") == second.call("ping")
        assert second.record.port == first.record.port
        opened = second.call("flow.open", {"flow": str(other / "sales.flow")})

    assert opened["flow"] == "sales"
    assert opened["path"] == str(other / "sales.flow")


def test_a_second_daemon_process_steps_aside(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")
    other = make_workspace(tmp_path / "other", flows=())

    with start(root) as live:
        held = live.call("ping")
        rival = subprocess.run(
            [sys.executable, "-m", "lumlflow.flow.daemon"],
            cwd=other,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert rival.returncode == ALREADY_RUNNING
        assert rival.stderr == ""
        assert "another lumlflow daemon is already running" in (
            workspace.log_path().read_text("utf-8")
        )
        assert live.call("ping") == held
        assert workspace.read_record() == live.record


def test_a_rival_steps_aside_even_with_no_record_to_read(
    tmp_path: Path, start: Starter
):
    """The record is what a verb calls; the lock is what a writer needs.

    Without one, a rival that finds no record — the file lost, or two verbs
    taking over one crashed daemon's workspace at the same instant — would
    open the same stores and append to the same journals.
    """
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        held = live.call("ping")
        workspace.record_path().unlink()

        rival = subprocess.run(
            [sys.executable, "-m", "lumlflow.flow.daemon"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # The lock is what turned it away: there was no record left to read.
        assert rival.returncode == ALREADY_RUNNING
        assert rival.stderr == ""
        assert "another lumlflow daemon is already running" in (
            workspace.log_path().read_text("utf-8")
        )
        assert live.call("ping") == held


def test_the_daemon_lock_is_held_by_one_holder_at_a_time() -> None:
    held = workspace.WorkspaceLock()
    rival = workspace.WorkspaceLock()

    assert held.acquire()
    try:
        assert not rival.acquire()
    finally:
        held.release()
        rival.release()

    assert rival.acquire()
    rival.release()


def test_a_record_whose_daemon_died_is_taken_over(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        dead = live.record
        os.kill(dead.pid, HARD_KILL)
        _wait_until_gone(dead)

    with client.connect(root) as fresh:
        assert fresh.record.pid != dead.pid
        assert fresh.record.instance_id != dead.instance_id
        assert workspace.read_record() == fresh.record
        _kill(fresh.record)


@pytest.mark.skipif(sys.platform == "win32", reason="requires kill -9 and /proc")
def test_a_kernel_outliving_a_dead_daemon_does_not_hold_the_lock(
    tmp_path: Path, start: Starter
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "gated", GATED_CELL)

    with start(root) as live, client.attach(live.record) as runner:
        live.call("flow.open", {"flow": "churn"})
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(
                runner.call, "run", {"flow": "churn", "target": "gated"}
            )
            kernel_pid = _wait_for_kernel(root)
            lock_target = str(workspace.lock_path().resolve())
            inherited = {
                Path(fd).resolve()
                for fd in Path(f"/proc/{kernel_pid}/fd").glob("*")
                if Path(fd).exists()
            }
            assert Path(lock_target) not in inherited

            os.kill(live.record.pid, HARD_KILL)
            _wait_until_gone(live.record)
            assert Path(f"/proc/{kernel_pid}").exists()

            with client.connect(root) as successor:
                assert successor.record.instance_id != live.record.instance_id
                assert workspace.lock_held()
                _kill(successor.record)

            (root / "go").write_text("", encoding="utf-8")
            with contextlib.suppress(Exception):
                running.result(timeout=30)


def test_daemon_stop_never_signals_a_pid_from_a_stale_record(
    tmp_path: Path, start: Starter, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        stale = live.record
        os.kill(stale.pid, HARD_KILL)
        _wait_until_gone(stale)

    signalled: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(
        client.os,
        "kill",
        lambda pid, sent: signalled.append((pid, sent)),
    )
    result = CliRunner().invoke(app, ["daemon", "stop"])

    assert result.exit_code == 0
    assert "no daemon was running" in result.output
    assert signalled == []
    assert workspace.read_record() is None


def test_daemon_stop_never_signals_a_record_replaced_by_a_successor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale = DaemonRecord(
        pid=101,
        instance_id="stale",
        port=1,
        token="old",
        web_host="127.0.0.1",
        web_port=5000,
        tracker_store="/tmp/experiments",
        version=__version__,
    )
    successor = DaemonRecord(
        pid=202,
        instance_id="successor",
        port=2,
        token="new",
        web_host="127.0.0.1",
        web_port=5000,
        tracker_store="/tmp/experiments",
        version=__version__,
    )
    signalled: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(workspace, "lock_held", lambda: True)
    monkeypatch.setattr(workspace, "read_record", lambda: successor)
    monkeypatch.setattr(
        client.os,
        "kill",
        lambda pid, sent: signalled.append((pid, sent)),
    )

    assert not client.stop(stale, timeout=0)
    assert signalled == []


def test_the_daemon_refuses_a_caller_without_its_token(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        forged = DaemonRecord(
            pid=live.record.pid,
            instance_id=live.record.instance_id,
            port=live.record.port,
            token="not-the-token",
            web_host=live.record.web_host,
            web_port=live.record.web_port,
            tracker_store=live.record.tracker_store,
            version=live.record.version,
        )
        wrong_instance = DaemonRecord(
            pid=live.record.pid,
            instance_id="another-daemon",
            port=live.record.port,
            token=live.record.token,
            web_host=live.record.web_host,
            web_port=live.record.web_port,
            tracker_store=live.record.tracker_store,
            version=live.record.version,
        )

        with pytest.raises(ServerError):
            with client.attach(forged, timeout=5) as intruder:
                intruder.call("ping")
        assert not client.is_alive(wrong_instance)


def test_shutdown_deregisters_and_a_restart_carries_the_store_forward(
    tmp_path: Path, start: Starter
):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    with start(root) as live:
        first = live.call("run", {"flow": "churn", "target": "score"})
        record = live.record
        live.call("shutdown")
    _wait_until_gone(record)
    _wait_until_deregistered(root)

    assert first["executed"] == ["score"]

    with client.connect(root) as restarted:
        try:
            assert restarted.record.pid != record.pid
            status = restarted.call("status", {"flow": "churn"})
            again = restarted.call("run", {"flow": "churn", "target": "score"})
        finally:
            _kill(restarted.record)

    # The kernel and the daemon were stateless; the store was not.
    assert [cell["state"] for cell in status["flows"][0]["cells"]] == ["synced"]
    assert (again["executed"], again["pruned"]) == ([], ["score"])


def test_shutdown_lets_go_of_the_workspace_with_a_client_still_attached(
    tmp_path: Path, start: Starter
):
    """A workbench tab, an MCP session, another verb — something is usually
    still connected when a daemon is told to stop. Waiting that connection out
    would strand the workspace: the record is cleared on the way down, so a
    daemon that hangs afterwards owns a workspace it is telling everyone is
    free, and every verb after it spawns a daemon that cannot take the lock.
    """
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        idle = client.attach(live.record)
        assert idle.call("ping")["pid"] == live.record.pid

        live.call("shutdown")
        _wait_until_deregistered(root)
        idle.close()

    # Deregistered means let go: the next verb's daemon can take the workspace.
    successor = workspace.WorkspaceLock()
    assert successor.acquire()
    successor.release()


def test_a_failure_crosses_the_wire_as_the_failure_it_was(
    tmp_path: Path, start: Starter
):
    root = make_workspace(tmp_path / "project", flows=("churn",))

    with start(root) as live:
        with pytest.raises(FlowNotFound) as missing:
            live.call("flow.open", {"flow": "sweep"})

    assert "`sweep`" in str(missing.value)


def test_a_200_kib_edit_keeps_a_leased_socket_session(
    tmp_path: Path, start: Starter
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "score", SCORE_CELL)
    source = f"{SCORE_CELL}\n# {'x' * (200 * 1024)}"

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        with client.attach(live.record, timeout=30) as paired:
            begun = paired.call(
                "agent.begin",
                {"flow": "churn", "actor": "codex", "label": "codex", "lease": True},
            )
            edited = paired.call(
                "cells.edit",
                {
                    "flow": "churn",
                    "slug": "score",
                    "source": source,
                    "intent": "large edit",
                    "actor": "codex",
                },
            )
            status = paired.call("status", {"flow": "churn"})

    assert begun["leased"] is True
    assert edited["slug"] == "score"
    assert status["flows"][0]["agent"] == "codex"
    assert "x" * (200 * 1024) in (flow_dir / "cells" / "score.py").read_text("utf-8")


def test_an_oversized_rpc_line_is_refused_without_dropping_the_connection(
    tmp_path: Path, start: Starter
) -> None:
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        connection = socket.create_connection(
            ("127.0.0.1", live.record.port), timeout=30
        )
        connection.settimeout(30)
        reader = connection.makefile("rb")
        try:
            connection.sendall(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "authenticate",
                        "params": {"token": live.record.token},
                    }
                ).encode()
                + b"\n"
            )
            connection.sendall(b"x" * (20 * 1024 * 1024) + b"\n")
            refused = json.loads(reader.readline())

            connection.sendall(
                b'{"jsonrpc":"2.0","id":7,"method":"ping","params":{}}\n'
            )
            answered = json.loads(reader.readline())
        finally:
            reader.close()
            connection.close()

    assert refused["id"] is None
    assert refused["error"]["code"] == INVALID_REQUEST
    assert "16 MiB" in refused["error"]["message"]
    assert answered["id"] == 7
    assert answered["result"]["pid"] == live.record.pid


def test_no_daemon_is_started_when_the_caller_says_not_to(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    with pytest.raises(ServerError):
        client.connect(root, start=False)

    assert workspace.read_record() is None


def test_an_mcp_client_that_is_killed_leaves_no_session_and_no_lock(
    tmp_path: Path, start: Starter, servers: Reap
):
    """The connection is the session, and this is what that buys.

    An agent that connects and is then killed — a terminal closed, a harness
    that crashed — never gets to say it finished. Nothing else can say it for
    it: the wrapper that used to bracket the process is gone, which is the
    point. So the daemon ends what the connection was carrying when the
    connection goes, and the flow it had taken the files of is free again
    without anybody forcing anything.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    command = harnesses.resolve_executable(
        Path(sys.executable).with_name("lumlflow"), search_path=""
    )
    if not Path(command).exists():
        pytest.skip("lumlflow is not installed as a console script here")

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        paired = subprocess.Popen(
            [command, "mcp", "--label", "pair-1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=str(root),
        )
        servers(paired)
        _say(paired, _hello())
        # A mutating tool: reading owns nothing, so nothing would be held.
        _say(
            paired,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "edit-cell",
                    "arguments": {
                        "slug": "score",
                        "source": SCORE_CELL.replace("0.91", "0.94"),
                        "intent": "swept",
                    },
                },
            },
        )
        working = _agent_of(live)

        os.kill(paired.pid, HARD_KILL)
        released = _until_unpaired(live)
        # No lock left behind: the checkout a human asks for next is not
        # refused on behalf of a process that is not there.
        checked_out = live.call("flow.checkout", {"flow": "churn", "branch": "main"})

    assert working == "pair-1"
    assert released is None
    assert checked_out["agent"] is None


def _hello() -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "1.0"},
        },
    }


def _say(process: "subprocess.Popen[bytes]", message: dict[str, Any]) -> Any:
    """One MCP message down stdin, and the answer back off stdout."""
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
    process.stdin.flush()
    return json.loads(process.stdout.readline())


def _agent_of(live: client.DaemonClient) -> str | None:
    """Who the flow says is working in its files, as the workbench reads it."""
    return live.call("status", {"flow": "churn"})["flows"][0]["agent"]


def _until_unpaired(live: client.DaemonClient, timeout: float = 30.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        paired = _agent_of(live)
        if paired is None:
            return None
        time.sleep(0.05)
    raise AssertionError("the flow is still paired")


def _wait_for_kernel(root: Path, timeout: float = 30.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        listed = subprocess.run(
            ["ps", "-eo", "pid=,args="], capture_output=True, text=True
        )
        for line in listed.stdout.splitlines():
            pid, _, command = line.strip().partition(" ")
            if pid.isdigit() and "lumlflow_kernel" in command and str(root) in command:
                return int(pid)
        time.sleep(0.05)
    raise AssertionError("the kernel did not start")


def test_a_browser_learns_who_is_paired_when_the_lease_opens_and_when_it_drops(
    tmp_path: Path, start: Starter
) -> None:
    """The connection is the session. A browser watching the flow is told the
    moment an agent registers over a leased socket, and told again — without
    anybody saying so — when that socket is gone.
    """
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    address = str(root / "churn.flow")

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        live.call("agent.begin", {"flow": "churn", "label": "manual"})
        with _watch(live.record, address) as socket:
            _caught_up(socket)
            paired = client.attach(live.record, timeout=30)
            paired.call(
                "agent.begin",
                {"flow": "churn", "actor": "codex", "label": "Codex", "lease": True},
            )
            live_frame = _until(
                socket,
                lambda frame: (
                    frame.get("type") == "agents"
                    and any(row["leased"] for row in frame["sessions"])
                ),
            )
            seen_by_tree = live.call("tree", {"flow": "churn"})["agent_sessions"]
            paired.close()
            dropped = _until(
                socket,
                lambda frame: (
                    frame.get("type") == "agents"
                    and not any(row["leased"] for row in frame["sessions"])
                ),
            )
        after = live.call("tree", {"flow": "churn"})["agent_sessions"]

    assert {(row["actor"], row["leased"]) for row in live_frame["sessions"]} == {
        ("codex", True),
        ("manual", False),
    }
    assert {(row["actor"], row["leased"]) for row in seen_by_tree} == {
        ("codex", True),
        ("manual", False),
    }
    # The end was committed for the dropped connection; the manual registration
    # is nobody's connection and stays, unleased.
    assert [(row["actor"], row["leased"]) for row in dropped["sessions"]] == [
        ("manual", False)
    ]
    assert [(row["actor"], row["leased"]) for row in after] == [("manual", False)]


def test_only_a_leased_caller_is_announced_as_working() -> None:
    """A CLI verb connects per call and holds no lease; the probes a harness
    sends say nothing about the flow. Everything else a leased connection
    calls is the agent working, on the cell the call names when it names one."""
    leased: set[tuple[str | None, str, str]] = {("/w/churn.flow", "codex-1", "Codex")}

    assert _activity(set(), "cells.edit", {"actor": "codex-1", "slug": "train"}) is None
    assert _activity(leased, "ping", {"actor": "codex-1"}) is None
    assert _activity(leased, "cells.edit", {"actor": "user", "slug": "train"}) is None
    assert _activity(leased, "cells.edit", {"actor": "codex-1", "slug": "train"}) == (
        "/w/churn.flow",
        "codex-1",
        "Codex",
        "cells.edit",
        "train",
    )
    assert _activity(leased, "run", {"actor": "codex-1", "target": "score.table"}) == (
        "/w/churn.flow",
        "codex-1",
        "Codex",
        "run",
        "score",
    )
    assert _activity(leased, "run", {"actor": "codex-1"}) == (
        "/w/churn.flow",
        "codex-1",
        "Codex",
        "run",
        None,
    )


def test_a_browser_is_told_what_a_leased_agent_is_doing_and_when_it_stops(
    tmp_path: Path, start: Starter
) -> None:
    """Every call a leased connection makes is bracketed for the flow's
    watchers: `started` with the cell it names before the daemon runs it,
    `ended` once it has answered. A connection that dies mid-call ends it too."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    address = str(root / "churn.flow")

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        with _watch(live.record, address) as socket:
            _caught_up(socket)
            paired = client.attach(live.record, timeout=30)
            paired.call(
                "agent.begin",
                {"flow": "churn", "actor": "codex", "label": "Codex", "lease": True},
            )
            paired.call(
                "cells.show", {"flow": "churn", "actor": "codex", "slug": "score"}
            )
            started = _until(
                socket,
                lambda frame: (
                    frame.get("type") == "activity" and frame.get("phase") == "started"
                ),
            )
            ended = _until(
                socket,
                lambda frame: (
                    frame.get("type") == "activity" and frame.get("phase") == "ended"
                ),
            )
            paired.close()
            _until(
                socket,
                lambda frame: (
                    frame.get("type") == "agents"
                    and not any(row["leased"] for row in frame["sessions"])
                ),
            )

    assert (started["actor"], started["label"], started["tool"], started["slug"]) == (
        "codex",
        "Codex",
        "cells.show",
        "score",
    )
    assert started["flow"] == address
    assert (ended["tool"], ended["slug"]) == ("cells.show", "score")


FENCE_NOTE = '''
class Note:
    """A note on the lane."""
'''
FENCED_AGENT = "codex-1"


def _fenced_agent(**params: Any) -> dict[str, Any]:
    return {"flow": "churn", "actor": FENCED_AGENT} | params


def test_a_leased_agent_is_refused_over_the_socket_and_nothing_lands(
    tmp_path: Path, start: Starter
) -> None:
    """The bracket the daemon puts around a leased call is where the fence is:
    the refusal crosses the wire as a `LaneMoved`, the lane keeps no trace of
    the change, and the agent's retry lands on the step it was moved to."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        live.call("cells.new", {"flow": "churn", "slug": "first", "source": FENCE_NOTE})
        first = live.call("cells.show", {"flow": "churn", "slug": "first"})
        live.call(
            "cells.new", {"flow": "churn", "slug": "second", "source": FENCE_NOTE}
        )

        paired = client.attach(live.record, timeout=30)
        try:
            paired.call(
                "agent.begin",
                {
                    "flow": "churn",
                    "actor": FENCED_AGENT,
                    "label": "Codex",
                    "lease": True,
                },
            )
            paired.call("context", _fenced_agent())
            live.call("rewind", {"flow": "churn", "to_step": first["created_step"]})

            with pytest.raises(FlowError) as refused:
                paired.call("cells.new", _fenced_agent(slug="third", source=FENCE_NOTE))
            behind = live.call("cells.list", {"flow": "churn"})["cells"]

            landed = paired.call(
                "cells.new", _fenced_agent(slug="third", source=FENCE_NOTE)
            )
            after = live.call("cells.list", {"flow": "churn"})["cells"]
        finally:
            paired.close()

    assert "moved to step" in str(refused.value)
    assert "Nothing was changed" in str(refused.value)
    assert {cell["slug"] for cell in behind} == {"score", "first"}
    assert landed["slug"] == "third"
    assert {cell["slug"] for cell in after} == {"score", "first", "third"}


def test_two_leased_agents_cannot_change_the_same_cell_at_once(
    tmp_path: Path, start: Starter
) -> None:
    """The first agent to name a cell holds it. The second is refused before
    anything lands and is never announced as on that cell; it can still read
    it. Once the first moves on, the cell is the second's to change."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    address = str(root / "churn.flow")
    edited = SCORE_CELL.replace("0.91", "0.95")

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        live.call("cells.new", {"flow": "churn", "slug": "notes", "source": FENCE_NOTE})
        codex = client.attach(live.record, timeout=30)
        claude = client.attach(live.record, timeout=30)
        try:
            for agent, actor, label in (
                (codex, "codex-1", "codex"),
                (claude, "claude-1", "claude-code"),
            ):
                agent.call(
                    "agent.begin",
                    {"flow": "churn", "actor": actor, "label": label, "lease": True},
                )
            with _watch(live.record, address) as socket:
                _caught_up(socket)
                codex.call(
                    "cells.show", {"flow": "churn", "actor": "codex-1", "slug": "score"}
                )
                held = _until(
                    socket,
                    lambda frame: frame.get("type") == "claims" and frame["claims"],
                )
                with pytest.raises(FlowError) as refused:
                    claude.call(
                        "cells.edit",
                        {
                            "flow": "churn",
                            "actor": "claude-1",
                            "slug": "score",
                            "source": edited,
                        },
                    )
                looked = claude.call(
                    "cells.show",
                    {"flow": "churn", "actor": "claude-1", "slug": "score"},
                )
                codex.call(
                    "cells.show", {"flow": "churn", "actor": "codex-1", "slug": "notes"}
                )
                claude.call(
                    "cells.edit",
                    {
                        "flow": "churn",
                        "actor": "claude-1",
                        "slug": "score",
                        "source": edited,
                    },
                )
                seen: list[dict[str, Any]] = []

                def edit_ended(frame: dict[str, Any]) -> bool:
                    seen.append(frame)
                    return (
                        frame.get("type") == "activity"
                        and frame.get("tool") == "cells.edit"
                        and frame.get("phase") == "ended"
                    )

                _until(socket, edit_ended)
        finally:
            codex.close()
            claude.close()

    assert [(claim["actor"], claim["slug"]) for claim in held["claims"]] == [
        ("codex-1", "score")
    ]
    assert "`score` is being worked on by codex" in str(refused.value)
    assert looked["slug"] == "score"
    # The refused edit was never announced: the only edit the watcher saw
    # is the one that landed after codex moved on.
    edits = [
        frame
        for frame in seen
        if frame.get("type") == "activity" and frame.get("tool") == "cells.edit"
    ]
    assert {frame["phase"] for frame in edits} == {"started", "ended"}
    assert len(edits) == 2
