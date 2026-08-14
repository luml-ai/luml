"""The kernel link: spawn, handshake, run, evict, restart, and death.

Every kernel here is a real process on a real socket — the point of these is
what happens across the boundary, which a stub could only assert about itself.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import kernel_proc
from lumlflow.flow.daemon.kernel_proc import spawn_environment
from lumlflow.flow.errors import KernelError
from lumlflow.flow.store.cas import Cas
from lumlflow.flow.store.flowstore import store_dir

import lumlflow_kernel
from tests.daemon.helpers import (
    fake_venv,
    flow_kernel,
    make_workspace,
    run_request,
    write_file,
)

SCORE = """
class Score:
    \"\"\"The headline metric.\"\"\"

    def materialize(self, ctx):
        print("scoring")
        return {"summary": {"auc": 0.91}}
"""

USES_HELPER = """
class UsesHelper:
    \"\"\"Reads a workspace helper.\"\"\"

    def materialize(self, ctx):
        import helpers

        return {"summary": {"value": helpers.VALUE}}
"""

CRASHES = """
class Crashes:
    \"\"\"Takes the kernel down with it.\"\"\"

    def materialize(self, ctx):
        import os

        os._exit(1)
"""

FAILS = """
class Fails:
    \"\"\"Raises.\"\"\"

    def materialize(self, ctx):
        raise ValueError("the model did not converge")
"""

SLEEPS = """
class Sleeps:
    \"\"\"Runs long enough to be interrupted.\"\"\"

    def materialize(self, ctx):
        import time

        for _ in range(2000):
            time.sleep(0.01)
        return {"summary": {"auc": 0.0}}
"""


async def test_the_handshake_reports_the_kernel_and_its_kinds(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        handshake = await kernel.ensure_started()

        assert handshake["protocol"] == lumlflow_kernel.PROTOCOL_VERSION
        assert handshake["implementation"] == "CPython"
        assert "run" in handshake["capabilities"]
        assert {"metric", "frame", "pickle"} <= {
            kind["kind"] for kind in handshake["kinds"]
        }
        assert kernel.state == "running"
        # Asking again attaches to the kernel there is, never a second one.
        assert (await kernel.ensure_started())["pid"] == handshake["pid"]


async def test_the_kernel_announces_itself_starting_and_stopping(tmp_path: Path):
    """The one fact a workbench cannot get any other way.

    A kernel starts lazily, on the first gesture that needs one, and nothing
    journals it — so a tab that read the state once when it opened would report
    "kernel not started" for the rest of its life, however many runs it watched
    go by. Restarting says both halves, in order, because a surface offering to
    restart has to see the one it asked for arrive.
    """
    root = make_workspace(tmp_path / "project")
    states: list[str] = []

    def record(event: str, params: dict[str, Any]) -> None:
        if event == kernel_proc.KERNEL_STATE_EVENT:
            states.append(str(params["state"]))

    async with flow_kernel(root, on_event=record) as kernel:
        await kernel.ensure_started()
        assert states == ["running"]

        # Attaching to the kernel there is announces nothing: nothing changed.
        await kernel.ensure_started()
        assert states == ["running"]

        await kernel.restart()
        assert states == ["running", "stopped", "running"]

        await kernel.stop()
        assert states == ["running", "stopped", "running", "stopped"]
        assert kernel.state == "stopped"


async def test_a_kernel_that_never_connected_reports_no_death(tmp_path: Path):
    """Stopping one that was never up would tell a surface a process died that
    never lived — and a workbench would draw a kernel going down it never saw
    come up."""
    root = make_workspace(tmp_path / "project")
    states: list[str] = []

    def record(event: str, params: dict[str, Any]) -> None:
        if event == kernel_proc.KERNEL_STATE_EVENT:
            states.append(str(params["state"]))

    async with flow_kernel(root, on_event=record) as kernel:
        await kernel.stop()

    assert states == []


async def test_a_cell_runs_and_its_value_lands_in_the_flows_store(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    events: list[tuple[str, dict[str, Any]]] = []

    def record(event: str, params: dict[str, Any]) -> None:
        events.append((event, params))

    async with flow_kernel(root, on_event=record) as kernel:
        result = await kernel.run(run_request("score", SCORE))

    assert result.state == "succeeded"
    summary = result.outputs["summary"]
    assert (summary.kind, summary.kind_source) == ("metric", "matcher")
    values = Cas(store_dir(root / "churn.flow") / "values")
    assert json.loads(values.get(str(summary.value_ref))) == {"auc": 0.91}
    assert result.cost_seconds is not None
    # The process coming up is announced before the run it came up for: a
    # surface learns there is a kernel from the kernel, not from the brief it
    # was handed before one existed.
    assert [name for name, _ in events][:2] == ["kernel_state", "started"]
    assert "log" in {name for name, _ in events}


async def test_a_failure_is_a_record_and_its_traceback_joins_the_logs(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        result = await kernel.run(run_request("fails", FAILS))

        assert result.state == "failed"
        assert result.outputs == {}
        logs = Cas(store_dir(root / "churn.flow") / "logs")
        artifact = logs.get(str(result.log_ref)).decode("utf-8")
        assert "the model did not converge" in artifact
        assert "ValueError" in artifact
        assert kernel.state == "running"


async def test_workspace_code_reloads_only_when_the_daemon_evicts_it(tmp_path: Path):
    root = make_workspace(tmp_path / "project", files={"helpers.py": "VALUE = 1"})

    async with flow_kernel(root) as kernel:
        first = await kernel.run(run_request("uses_helper", USES_HELPER))
        write_file(root / "helpers.py", "VALUE = 2")
        stale = await kernel.run(run_request("uses_helper", USES_HELPER, run_id="r2"))
        evicted = await kernel.evict_workspace_modules()
        fresh = await kernel.run(run_request("uses_helper", USES_HELPER, run_id="r3"))

    values = Cas(store_dir(root / "churn.flow") / "values")
    read = [
        json.loads(values.get(str(result.outputs["summary"].value_ref)))["value"]
        for result in (first, stale, fresh)
    ]
    assert read == [1, 1, 2]
    assert "helpers" in evicted


async def test_a_kernel_that_dies_names_the_cell_and_the_next_run_respawns(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        first = await kernel.ensure_started()
        with pytest.raises(KernelError) as died:
            await kernel.run(run_request("crashes", CRASHES))

        assert "`crashes`" in str(died.value)
        assert kernel.state == "stopped"

        result = await kernel.run(run_request("score", SCORE, run_id="after"))

        assert result.state == "succeeded"
        assert kernel.handshake is not None
        assert kernel.handshake["pid"] != first["pid"]


async def test_restart_is_a_new_process_and_forgets_nothing_the_store_holds(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        before = await kernel.ensure_started()
        after = await kernel.restart()

        assert after["pid"] != before["pid"]
        assert (await kernel.run(run_request("score", SCORE))).state == "succeeded"


@pytest.mark.skipif(
    sys.platform == "win32", reason="the stand-in venv is a symlink to this python"
)
async def test_the_kernel_runs_on_the_workspace_venv_when_there_is_one(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    python = fake_venv(root)

    async with flow_kernel(root) as kernel:
        await kernel.ensure_started()

        assert kernel.interpreter is not None
        assert (kernel.interpreter.python, kernel.interpreter.source) == (
            python,
            "venv",
        )


async def test_a_cancel_reaches_a_run_that_is_already_going(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    started = asyncio.Event()

    def watch(event: str, params: dict[str, Any]) -> None:
        if event == "started":
            started.set()

    async with flow_kernel(root, on_event=watch) as kernel:
        running = asyncio.ensure_future(
            kernel.run(run_request("sleeps", SLEEPS, run_id="sleeper"))
        )
        await asyncio.wait_for(started.wait(), timeout=30)
        kernel.cancel("sleeper")
        result = await asyncio.wait_for(running, timeout=30)

        assert result.state == "cancelled"
        assert kernel.state == "running"


def test_the_kernel_is_path_injected_and_the_workspace_rides_along(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project")
    monkeypatch.setenv("PYTHONPATH", "/already/on/the/path")

    spawned = spawn_environment(root)

    entries = spawned["PYTHONPATH"].split(os.pathsep)
    assert Path(entries[0]) == Path(lumlflow_kernel.__file__).resolve().parent.parent
    assert entries[1] == str(root)
    assert entries[2] == "/already/on/the/path"


async def test_a_stopped_kernel_has_nothing_to_evict(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        assert await kernel.evict_workspace_modules() == []
        assert kernel.state == "stopped"


class TestLoopbackTransport:
    """The other transport, exercised where unix sockets exist.

    Windows has no unix domain sockets and a deep temp directory beats macOS's
    path limit, so the link falls back to loopback plus a daemon-minted token.
    Shortening the limit to nothing is how a POSIX box takes that route — the
    same branch, reached by the same question, on a platform CI can run.
    """

    @pytest.fixture(autouse=True)
    def unbindable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(kernel_proc, "_UNIX_PATH_LIMIT", 0)

    async def test_the_kernel_dials_a_port_and_a_cell_runs_over_it(
        self, tmp_path: Path
    ):
        root = make_workspace(tmp_path / "project")

        async with flow_kernel(root) as kernel:
            handshake = await kernel.ensure_started()
            result = await kernel.run(run_request("score", SCORE))

            kernel_dir = store_dir(root / "churn.flow") / kernel_proc.KERNEL_DIRNAME
            assert not (kernel_dir / kernel_proc.SOCKET_NAME).exists()
            assert (kernel_dir / kernel_proc.TOKEN_NAME).read_text("utf-8")
            assert handshake["protocol"] == lumlflow_kernel.PROTOCOL_VERSION
            assert result.state == "succeeded"

    async def test_a_caller_that_cannot_prove_the_token_never_becomes_the_link(
        self, tmp_path: Path
    ):
        """A port on loopback is reachable by everything on the machine, so the
        first line has to prove this is the kernel the daemon spawned."""
        root = make_workspace(tmp_path / "project")

        async with flow_kernel(root) as kernel:
            address, token_file = await kernel._listen()
            assert token_file is not None

            refused, refused_writer = await _greet(address, "not-the-token")

            # Waited on rather than read to the end: a link that wrongly took
            # this caller would hold the connection open, and a test that hung
            # on that would report a regression as a suite that never finishes.
            assert await asyncio.wait_for(refused.read(), timeout=10) == b""
            assert not kernel._connected.is_set()
            refused_writer.close()

            _, accepted = await _greet(address, token_file.read_text("utf-8"))

            await asyncio.wait_for(kernel._connected.wait(), timeout=10)
            accepted.close()


async def _greet(
    address: str, token: str
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Dial the daemon's port the way the kernel does, token first."""
    host, _, port = address.rpartition(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(
        json.dumps({"method": "authenticate", "params": {"token": token}}).encode()
        + b"\n"
    )
    await writer.drain()
    return reader, writer
