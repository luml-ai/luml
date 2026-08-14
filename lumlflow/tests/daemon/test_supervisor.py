"""The supervisor: one daemon per workspace, started by whoever needs it.

These run the real thing — `python -m lumlflow.flow.daemon` in its own process,
reached over its loopback socket — because the singleton, the discovery record
and the restart are only true if they are true across processes.
"""

import contextlib
import json
import os
import signal
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
from lumlflow.flow.daemon import client, connect, web, workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowNotFound, ServerError

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
        if workspace.read_record(root) is None:
            return
        time.sleep(0.05)
    raise AssertionError("the daemon is still registered")


def test_a_verb_that_finds_no_daemon_starts_one(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        status = live.call("status")

        record = workspace.read_record(root)
        assert record is not None
        assert record.workspace == str(root)
        assert record.port > 0 and record.token
        assert status["workspace"] == str(root)
        assert status["pid"] == record.pid
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
        record = workspace.read_record(root)
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
        _kill(workspace.read_record(root))


def test_a_verb_waits_out_a_workspace_that_is_briefly_held(tmp_path: Path):
    """A daemon that finds the workspace taken exits at once. The verb that
    started it still needs a daemon, so it tries again rather than failing."""
    root = make_workspace(tmp_path / "project")
    lock = workspace.WorkspaceLock(root)
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
        _kill(workspace.read_record(root))


def test_a_second_verb_reuses_the_daemon_that_is_already_there(
    tmp_path: Path, start: Starter
):
    root = make_workspace(tmp_path / "project")

    with start(root) as first, client.connect(root) as second:
        assert first.call("ping") == second.call("ping")
        assert second.record.port == first.record.port


def test_a_second_daemon_for_one_workspace_steps_aside(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        held = live.call("ping")
        rival = subprocess.run(
            [sys.executable, "-m", "lumlflow.flow.daemon", "--workspace", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert rival.returncode == 1
        assert rival.stderr.strip() == f"another lumlflow server holds {root}"
        assert live.call("ping") == held
        assert workspace.read_record(root) == live.record


def test_a_daemon_defers_to_a_live_record_when_the_lock_does_not_hold(
    tmp_path: Path, start: Starter
):
    """Not every filesystem honours an advisory lock, so the record is the
    second line of defense: a daemon that answers is a daemon that owns."""
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        held = live.call("ping")
        workspace.record_path(root).with_suffix(".lock").unlink()

        rival = subprocess.run(
            [sys.executable, "-m", "lumlflow.flow.daemon", "--workspace", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert rival.returncode == 1
        assert f"already owns {root} (pid {held['pid']})" in rival.stderr
        assert live.call("ping") == held


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
        workspace.record_path(root).unlink()

        rival = subprocess.run(
            [sys.executable, "-m", "lumlflow.flow.daemon", "--workspace", str(root)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # The lock is what turned it away: there was no record left to read.
        assert rival.returncode == 1
        assert rival.stderr.strip() == f"another lumlflow server holds {root}"
        assert live.call("ping") == held


def test_the_workspace_lock_is_held_by_one_holder_at_a_time(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    held = workspace.WorkspaceLock(root)
    rival = workspace.WorkspaceLock(root)

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
        assert workspace.read_record(root) == fresh.record
        _kill(fresh.record)


def test_the_daemon_refuses_a_caller_without_its_token(tmp_path: Path, start: Starter):
    root = make_workspace(tmp_path / "project")

    with start(root) as live:
        forged = DaemonRecord(
            workspace=live.record.workspace,
            pid=live.record.pid,
            port=live.record.port,
            token="not-the-token",
            started=live.record.started,
        )

        with pytest.raises(ServerError):
            with client.attach(forged, timeout=5) as intruder:
                intruder.call("ping")


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
    successor = workspace.WorkspaceLock(root)
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


def test_no_daemon_is_started_when_the_caller_says_not_to(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    with pytest.raises(ServerError):
        client.connect(root, start=False)

    assert workspace.read_record(root) is None


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
    command = connect.executable()
    if not Path(command).exists():
        pytest.skip("lumlflow is not installed as a console script here")

    with start(root) as live:
        live.call("flow.open", {"flow": "churn"})
        paired = subprocess.Popen(
            [command, "mcp", "--workspace", str(root), "--label", "pair-1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=str(tmp_path),
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
