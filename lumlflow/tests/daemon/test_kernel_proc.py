import asyncio
import json
import os
import sys
import tempfile
from base64 import b64decode
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

PRINTS_LARGE = """
class PrintsLarge:
    \"\"\"Writes one large console value.\"\"\"

    def materialize(self, ctx):
        print("x" * 200_000, end="")
        return {"summary": {"written": 200_000}}
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
        assert (await kernel.ensure_started())["pid"] == handshake["pid"]


async def test_the_kernel_announces_itself_starting_and_stopping(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    states: list[str] = []

    def record(event: str, params: dict[str, Any]) -> None:
        if event == kernel_proc.KERNEL_STATE_EVENT:
            states.append(str(params["state"]))

    async with flow_kernel(root, on_event=record) as kernel:
        await kernel.ensure_started()
        assert states == ["running"]

        await kernel.ensure_started()
        assert states == ["running"]

        await kernel.restart()
        assert states == ["running", "stopped", "running"]

        await kernel.stop()
        assert states == ["running", "stopped", "running", "stopped"]
        assert kernel.state == "stopped"


async def test_a_kernel_that_never_connected_reports_no_death(tmp_path: Path):
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
    assert [name for name, _ in events][:2] == ["kernel_state", "started"]
    assert "log" in {name for name, _ in events}


async def test_a_200_000_character_print_stays_on_one_kernel_and_arrives_whole(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    events: list[tuple[str, dict[str, Any]]] = []

    def record(event: str, params: dict[str, Any]) -> None:
        events.append((event, params))

    async with flow_kernel(root, on_event=record) as kernel:
        handshake = await kernel.ensure_started()
        result = await kernel.run(run_request("prints_large", PRINTS_LARGE))
        chunks = [
            b64decode(params["bytes"]) for event, params in events if event == "log"
        ]

        assert result.state == "succeeded"
        assert b"".join(chunks) == b"x" * 200_000
        assert max(map(len, chunks)) <= 32 * 1024
        assert kernel.state == "running"
        assert kernel.handshake is not None
        assert kernel.handshake["pid"] == handshake["pid"]


async def test_an_oversized_kernel_message_fails_the_run_but_keeps_the_link(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        address, token_file = await kernel._listen()
        if token_file is None:
            peer_reader, peer_writer = await asyncio.open_unix_connection(address)
        else:
            peer_reader, peer_writer = await _greet(
                address, token_file.read_text("utf-8")
            )
        await asyncio.wait_for(kernel._connected.wait(), timeout=10)
        kernel.handshake = {"pid": 1234}

        rejected = asyncio.create_task(
            kernel.run(run_request("score", SCORE, run_id="too-large"))
        )
        request = json.loads(await peer_reader.readline())
        peer_writer.write(f'{{"jsonrpc":"2.0","id":{request["id"]},"result":"'.encode())
        peer_writer.write(b"x" * (17 * 1024 * 1024))
        peer_writer.write(b'"}\n')
        await peer_writer.drain()

        with pytest.raises(KernelError, match="16 MiB") as overrun:
            await rejected

        assert "stopped" not in str(overrun.value)
        assert kernel.state == "running"

        next_run = asyncio.create_task(
            kernel.run(run_request("score", SCORE, run_id="after-limit"))
        )
        next_request = json.loads(await peer_reader.readline())
        peer_writer.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": next_request["id"],
                    "result": {"state": "succeeded", "outputs": {}},
                }
            ).encode()
            + b"\n"
        )
        await peer_writer.drain()

        assert (await next_run).state == "succeeded"
        assert kernel.state == "running"
        peer_writer.close()
        await peer_writer.wait_closed()


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


async def test_workspace_code_reloads_after_eviction_is_requested(tmp_path: Path):
    root = make_workspace(tmp_path / "project", files={"helpers.py": "VALUE = 1"})

    async with flow_kernel(root) as kernel:
        first = await kernel.run(run_request("uses_helper", USES_HELPER))
        write_file(root / "helpers.py", "VALUE = 2")
        stale = await kernel.run(run_request("uses_helper", USES_HELPER, run_id="r2"))
        kernel.evict_workspace_modules()
        fresh = await kernel.run(run_request("uses_helper", USES_HELPER, run_id="r3"))

    values = Cas(store_dir(root / "churn.flow") / "values")
    read = [
        json.loads(values.get(str(result.outputs["summary"].value_ref)))["value"]
        for result in (first, stale, fresh)
    ]
    assert read == [1, 1, 2]


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


def test_only_the_staged_kernel_package_precedes_the_workspace_on_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project")
    monkeypatch.setenv("PYTHONPATH", "/already/on/the/path")

    entries = spawn_environment(root)["PYTHONPATH"].split(os.pathsep)

    install_dir = Path(lumlflow_kernel.__file__).resolve().parent.parent
    assert [path.name for path in Path(entries[0]).iterdir()] == ["lumlflow_kernel"]
    assert entries[1:] == [str(root), "/already/on/the/path"]
    assert all(Path(entry).resolve() != install_dir for entry in entries)


def staged_files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_the_staged_package_matches_the_install_and_a_rebuild_writes_nothing(
    tmp_path: Path, state_dir: Path
):
    root = make_workspace(tmp_path / "project")
    installed = Path(lumlflow_kernel.__file__).resolve().parent

    staged = Path(spawn_environment(root)["PYTHONPATH"].split(os.pathsep)[0])
    stamps = {path: path.stat().st_mtime_ns for path in staged.rglob("*")}
    rebuilt = Path(spawn_environment(root)["PYTHONPATH"].split(os.pathsep)[0])

    assert rebuilt == staged
    assert staged.is_relative_to(state_dir)
    assert staged_files(staged / "lumlflow_kernel") == staged_files(installed)
    assert {path: path.stat().st_mtime_ns for path in staged.rglob("*")} == stamps
    assert [path.name for path in staged.parent.iterdir()] == [staged.name]


def test_a_changed_install_is_restaged_on_the_next_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = make_workspace(tmp_path / "project")
    installed = tmp_path / "site-packages" / "lumlflow_kernel"
    write_file(installed / "__init__.py", "VERSION = 1\n")
    write_file(installed / "kinds" / "__init__.py", "")
    monkeypatch.setattr(lumlflow_kernel, "__file__", str(installed / "__init__.py"))
    before = Path(spawn_environment(root)["PYTHONPATH"].split(os.pathsep)[0])

    write_file(installed / "__init__.py", "VERSION = 2\n")
    after = Path(spawn_environment(root)["PYTHONPATH"].split(os.pathsep)[0])

    assert after != before
    assert staged_files(after / "lumlflow_kernel") == staged_files(installed)
    assert [path.name for path in after.iterdir()] == ["lumlflow_kernel"]


def test_a_copy_another_start_staged_first_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    installed = tmp_path / "site-packages" / "lumlflow_kernel"
    write_file(installed / "__init__.py", "VERSION = 1\n")
    real_mkdtemp = tempfile.mkdtemp
    winners: list[tuple[Path, int]] = []

    def raced(**options: Any) -> str:
        monkeypatch.setattr(tempfile, "mkdtemp", real_mkdtemp)
        winner = kernel_proc.stage_kernel_package(installed)
        stamp = (winner / "lumlflow_kernel" / "__init__.py").stat().st_mtime_ns
        winners.append((winner, stamp))
        return real_mkdtemp(**options)

    monkeypatch.setattr(tempfile, "mkdtemp", raced)

    staged = kernel_proc.stage_kernel_package(installed)

    [(winner, stamp)] = winners
    assert staged == winner
    assert (staged / "lumlflow_kernel" / "__init__.py").stat().st_mtime_ns == stamp
    assert [path.name for path in staged.parent.iterdir()] == [staged.name]


async def test_requesting_eviction_does_not_start_a_stopped_kernel(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    async with flow_kernel(root) as kernel:
        kernel.evict_workspace_modules()
        assert kernel.state == "stopped"


class TestLoopbackTransport:
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
        root = make_workspace(tmp_path / "project")

        async with flow_kernel(root) as kernel:
            address, token_file = await kernel._listen()
            assert token_file is not None

            refused, refused_writer = await _greet(address, "not-the-token")

            assert await asyncio.wait_for(refused.read(), timeout=10) == b""
            assert not kernel._connected.is_set()
            refused_writer.close()

            _, accepted = await _greet(address, token_file.read_text("utf-8"))

            await asyncio.wait_for(kernel._connected.wait(), timeout=10)
            accepted.close()


async def _greet(
    address: str, token: str
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    host, _, port = address.rpartition(":")
    reader, writer = await asyncio.open_connection(host, int(port))
    writer.write(
        json.dumps({"method": "authenticate", "params": {"token": token}}).encode()
        + b"\n"
    )
    await writer.drain()
    return reader, writer
