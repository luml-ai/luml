import asyncio
import threading
from pathlib import Path

import pytest
from lumlflow.flow.daemon import hub as hub_module
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import Hub
from lumlflow.flow.daemon.main import Daemon
from lumlflow.flow.daemon.workspace import FlowRef
from lumlflow.flow.dsl.tree import ScanStopped, WorkspaceTree, scan_workspace
from lumlflow.flow.errors import FlowError, FlowNotFound
from lumlflow.flow.store.flowstore import store_dir
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


class _FirstScanFails(_BlockedScan):
    """The first scan is held until released and then finds the tree
    unreadable; every later one reads it."""

    def __call__(
        self, workspace_dir: Path, *, stopping: threading.Event | None = None
    ) -> WorkspaceTree:
        if self.calls:
            return scan_workspace(workspace_dir, stopping=stopping)
        self.calls += 1
        self.entered.set()
        self.release.wait(_PROMPT_S * 5)
        raise PermissionError(13, "permission denied", str(workspace_dir))


async def test_an_open_waiting_behind_a_delete_does_not_recreate_the_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        ref = api.resolve("churn")
        scan = _FirstScanFails()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        opening = asyncio.create_task(api.hub.open(ref))
        await scan.started()
        deleting = asyncio.create_task(api.hub.delete_flow(ref))
        reading = asyncio.create_task(api.hub.open(ref))
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        scan.release.set()
        with pytest.raises(PermissionError):
            await asyncio.wait_for(opening, _PROMPT_S)
        await asyncio.wait_for(deleting, _PROMPT_S)
        with pytest.raises(FlowNotFound):
            await asyncio.wait_for(reading, _PROMPT_S)
        left = api.hub.attached(ref.path)

    assert left is None
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


def _link(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("this system does not let the tests make directory links")


async def test_a_symlink_and_its_target_opened_together_share_one_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    _link(root / "alias.flow", root / "churn.flow")
    alias = FlowRef(name="alias", path=root / "alias.flow", relpath="alias.flow")

    async with daemon_api(root) as api:
        target = api.resolve(str(root / "churn.flow"))
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        through_alias = asyncio.create_task(api.hub.open(alias))
        await scan.started()
        through_target = asyncio.create_task(api.hub.open(target))
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        scan.release.set()
        first = await asyncio.wait_for(through_alias, _PROMPT_S)
        second = await asyncio.wait_for(through_target, _PROMPT_S)
        opened = api.hub.opened()
        attached = api.hub.attached(alias.path)

    assert second is first
    assert opened == [first]
    assert attached is first
    assert first.ref.name == "alias"
    assert first.ref.path == alias.path


async def test_deleting_a_symlink_opened_by_its_name_keeps_its_target(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    cell = write_cell(root / "churn.flow", "score", SCORE_CELL)
    _link(root / "alias.flow", root / "churn.flow")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "alias"})
        with pytest.raises(FlowError, match="is a link"):
            await api.flow_delete({"flow": "alias"})
        still_open = api.hub.attached(root / "churn.flow")

    assert still_open is not None
    assert cell.is_file()
    assert store_dir(root / "churn.flow").is_dir()


async def test_a_flow_created_under_a_linked_directory_shares_its_first_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    (root / "real").mkdir()
    _link(root / "linked", root / "real")
    real = FlowRef(name="new", path=root / "real" / "new.flow", relpath="real/new.flow")

    async with daemon_api(root) as api:
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        creating = asyncio.create_task(api.hub.init_flow(root, "linked/new"))
        await scan.started()
        opening = asyncio.create_task(api.hub.open(real))
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        scan.release.set()
        created = await asyncio.wait_for(creating, _PROMPT_S)
        opened = await asyncio.wait_for(opening, _PROMPT_S)
        sessions = api.hub.opened()

    assert opened is created
    assert sessions == [created]


async def test_renaming_a_flow_through_its_symlink_closes_the_open_session(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    _link(root / "alias.flow", root / "churn.flow")
    alias = FlowRef(name="alias", path=root / "alias.flow", relpath="alias.flow")

    async with daemon_api(root) as api:
        await api.hub.open(alias)
        renamed = await api.hub.rename_flow(alias, "other")
        opened = api.hub.opened()

    assert opened == []
    assert renamed.path == root / "other.flow"
    assert renamed.path.is_symlink()


async def test_stopping_after_a_waiting_caller_left_stops_the_run_that_stayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        staying = asyncio.create_task(api.run({"flow": "churn"}))
        await scan.started()
        leaving = asyncio.create_task(api.run({"flow": "churn"}))
        for _ in range(_YIELDS):
            await asyncio.sleep(0)
        await _cancelled(leaving)
        left = await api.cancel({"flow": "churn"})
        scan.release.set()
        outcome = await asyncio.wait_for(staying, _PROMPT_S)
        left_after = await api.cancel({"flow": "churn"})

    assert left["left"] == 1
    assert (outcome["abandoned"], outcome["executed"]) == (True, [])
    assert left_after["left"] == 0


async def test_a_second_stop_does_not_count_a_run_already_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        running = asyncio.create_task(api.run({"flow": "churn"}))
        await scan.started()
        first = await api.cancel({"flow": "churn"})
        second = await api.cancel({"flow": "churn"})
        scan.release.set()
        outcome = await asyncio.wait_for(running, _PROMPT_S)

    assert (first["left"], second["left"]) == (1, 0)
    assert outcome["abandoned"]


async def test_a_run_waiting_for_its_scan_keeps_the_daemon_from_idling_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    daemon = Daemon(root)
    try:
        await daemon.api.flow_open({"flow": "churn"})
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        running = asyncio.create_task(daemon.api.run({"flow": "churn"}))
        await scan.started()
        idle = await daemon.api.shutdown_if_idle({"path": str(root / "churn.flow")})
        scan.release.set()
        await asyncio.wait_for(running, _PROMPT_S)
    finally:
        await daemon.hub.close()

    assert not idle["stopping"]
    assert idle["attached"]["active_runs"] == 1


async def test_a_stopped_run_still_waiting_for_its_scan_lets_the_daemon_idle_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    daemon = Daemon(root)
    try:
        await daemon.api.flow_open({"flow": "churn"})
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        running = asyncio.create_task(daemon.api.run({"flow": "churn"}))
        await scan.started()
        await daemon.api.cancel({"flow": "churn"})
        idle = await daemon.api.shutdown_if_idle({"path": str(root / "churn.flow")})
        scan.release.set()
        await asyncio.wait_for(running, _PROMPT_S)
    finally:
        await daemon.hub.close()

    assert idle["attached"]["active_runs"] == 0


async def test_open_flows_count_a_run_waiting_for_its_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        scan = _BlockedScan()
        monkeypatch.setattr(hub_module, "scan_workspace", scan)
        running = asyncio.create_task(api.run({"flow": "churn"}))
        await scan.started()
        listed = await api.flows_open({})
        scan.release.set()
        await asyncio.wait_for(running, _PROMPT_S)

    assert [flow["active_runs"] for flow in listed["flows"]] == [1]
    assert listed["totals"]["active_runs"] == 1
