import asyncio
import threading
from pathlib import Path

import pytest
from lumlflow.flow.daemon import hub as hub_module
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.dsl.tree import ScanStopped, WorkspaceTree, scan_workspace

from tests.helpers.daemon import SCORE_CELL, daemon_api, make_workspace, write_cell

_PROMPT_S = 2.0
# Enough turns of the loop for a coroutine with no I/O to reach the lock.
_YIELDS = 50


class _BlockedScan:
    """Stands in for `scan_workspace`: holds each scan until released, the
    way a scan of a very large tree would, and honours the stop the hub asks."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def __call__(
        self, workspace_dir: Path, *, stopping: threading.Event | None = None
    ) -> WorkspaceTree:
        self.calls += 1
        self.entered.set()
        while not self.release.wait(0.01):
            if stopping is not None and stopping.is_set():
                break
        return scan_workspace(workspace_dir, stopping=stopping)

    async def started(self) -> None:
        assert await asyncio.to_thread(self.entered.wait, _PROMPT_S)


async def test_the_loop_answers_while_a_scan_is_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        quiescing = asyncio.create_task(api.hub.quiesce(session))
        await scan.started()
        answered = await asyncio.wait_for(api.ping({}), _PROMPT_S)
        listed = await asyncio.wait_for(api.workspace_list({}), _PROMPT_S)
        still_scanning = not quiescing.done()
        scan.release.set()
        await quiescing

    assert answered
    assert listed
    assert still_scanning


async def test_two_scans_of_one_workspace_never_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.flow_open({"flow": "sales"})
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        first = asyncio.create_task(api.hub.quiesce(api.hub.session("churn")))
        await scan.started()
        second = asyncio.create_task(api.hub.quiesce(api.hub.session("sales")))
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        while_blocked = scan.calls
        scan.release.set()
        await asyncio.gather(first, second)

    assert while_blocked == 1
    assert scan.calls == 2


async def test_closing_during_a_blocked_scan_ends_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    hub = Hub()
    api = Api(hub, directory=root)
    await api.flow_open({"flow": "churn"})
    scan = _BlockedScan()
    monkeypatch.setattr(hub_module, "scan_workspace", scan)
    quiescing = asyncio.create_task(hub.quiesce(hub.session("churn")))
    await scan.started()

    await asyncio.wait_for(hub.close(), _PROMPT_S)

    with pytest.raises(ScanStopped):
        await quiescing
    assert not [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith("lumlflow-scan")
    ]
