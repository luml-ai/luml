import asyncio
import threading
from pathlib import Path

import pytest
from lumlflow.flow.daemon import hub as hub_module
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.dsl.tree import ScanStopped, WorkspaceTree, scan_workspace
from lumlflow.flow.store.models import RunRecorded

from tests.helpers.daemon import (
    SCORE_CELL,
    daemon_api,
    make_workspace,
    ops_of,
    slice_of,
    write_cell,
)

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


class _StubbornScan(_BlockedScan):
    """A scan that does not look at its stop flag until released: a thread
    deep in one huge directory listing."""

    def __init__(self) -> None:
        super().__init__()
        self._running = 0
        self.overlapped = False
        self._lock = threading.Lock()

    def __call__(
        self, workspace_dir: Path, *, stopping: threading.Event | None = None
    ) -> WorkspaceTree:
        with self._lock:
            self.calls += 1
            self._running += 1
            self.overlapped |= self._running > 1
        self.entered.set()
        try:
            self.release.wait(_PROMPT_S * 5)
            return scan_workspace(workspace_dir, stopping=stopping)
        finally:
            with self._lock:
                self._running -= 1


async def _cancelled(task: "asyncio.Task[object]") -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, _PROMPT_S)


async def test_a_cancelled_first_open_leaves_no_half_open_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        ref = api.resolve("churn")
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        opening = asyncio.create_task(api.hub.open(ref))
        await scan.started()
        await _cancelled(opening)
        left = (api.hub.attached(ref.path), api.hub.watches.roots())
        monkeypatch.setattr(hub_module, "scan_workspace", scan_workspace)
        reopened = await asyncio.wait_for(api.hub.open(ref), _PROMPT_S)
        synced = reopened.store.index.workspace_tree() is not None
        accepted = sorted(slice_of(reopened, "main"))

    assert left == (None, [])
    assert (synced, accepted) == (True, ["score"])


async def test_a_first_open_whose_scan_fails_leaves_no_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    def unreadable(workspace_dir: Path, **kwargs: object) -> WorkspaceTree:
        raise PermissionError(13, "permission denied", str(workspace_dir))

    async with daemon_api(root) as api:
        ref = api.resolve("churn")
        monkeypatch.setattr(hub_module, "scan_workspace", unreadable)
        with pytest.raises(PermissionError):
            await api.hub.open(ref)
        left = (api.hub.attached(ref.path), api.hub.watches.roots())
        monkeypatch.setattr(hub_module, "scan_workspace", scan_workspace)
        reopened = await api.hub.open(ref)
        synced = reopened.store.index.workspace_tree() is not None

    assert left == (None, [])
    assert synced


async def test_a_cancelled_scan_keeps_its_workspace_until_its_thread_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        scan = _StubbornScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        first = asyncio.create_task(api.hub.quiesce(session))
        await scan.started()
        first.cancel()
        retries = [asyncio.create_task(api.hub.quiesce(session)) for _ in range(3)]
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        while_stuck = (scan.calls, first.done())
        scan.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, _PROMPT_S)
        await asyncio.wait_for(asyncio.gather(*retries), _PROMPT_S)

    assert while_stuck == (1, False)
    assert not scan.overlapped


async def test_deleting_a_flow_mid_first_open_waits_for_the_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        ref = api.resolve("churn")
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        opening = asyncio.create_task(api.hub.open(ref))
        await scan.started()
        deleting = asyncio.create_task(api.hub.delete_flow(ref))
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        deleted_early = deleting.done()
        scan.release.set()
        await asyncio.wait_for(opening, _PROMPT_S)
        await asyncio.wait_for(deleting, _PROMPT_S)
        left = (api.hub.attached(ref.path), api.hub.watches.roots())

    assert not deleted_early
    assert left == (None, [])
    assert not ref.path.exists()


async def test_closing_the_hub_mid_first_open_ends_the_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    hub = Hub()
    api = Api(hub, directory=root)
    ref = api.resolve("churn")
    scan = _BlockedScan()
    monkeypatch.setattr(hub_module, "scan_workspace", scan)
    opening = asyncio.create_task(hub.open(ref))
    await scan.started()

    await asyncio.wait_for(hub.close(), _PROMPT_S)

    with pytest.raises(ScanStopped):
        await opening
    assert (hub.attached(ref.path), hub.watches.roots()) == (None, [])


async def test_stopping_a_run_that_waits_for_its_scan_runs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    marker = tmp_path / "executed"
    write_cell(
        root / "churn.flow",
        "leaf",
        f"""
        class Leaf:
            produces = {{"value": "asset"}}

            def materialize(self, ctx):
                from pathlib import Path

                Path({str(marker)!r}).touch()
                return {{"value": 1}}
        """,
    )

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        running = asyncio.create_task(api.run({"flow": "churn"}))
        await scan.started()
        left = await api.cancel({"flow": "churn"})
        scan.release.set()
        outcome = await asyncio.wait_for(running, _PROMPT_S)
        runs = ops_of(session, RunRecorded)

    assert left["left"] == 1
    assert (outcome["abandoned"], outcome["executed"]) == (True, [])
    assert runs == []
    assert not marker.exists()
