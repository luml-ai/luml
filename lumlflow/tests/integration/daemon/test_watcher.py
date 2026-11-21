import asyncio
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import hub as hub_module
from lumlflow.flow.daemon import watcher as watcher_module
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.daemon.reconcile import MIXED_EDITING
from lumlflow.flow.daemon.watcher import Watcher, Watches, WatchSet
from lumlflow.flow.dsl.tree import WorkspaceTree, scan_workspace
from lumlflow.flow.store.flowstore import manifest_path, store_dir
from lumlflow.flow.store.models import FlagSet

from tests.helpers.daemon import (
    SCORE_CELL,
    daemon_api,
    make_workspace,
    opened,
    slice_of,
    transactions,
    write_cell,
    write_file,
)

_DEBOUNCE_S = 0.05
_DELIVERY_TIMEOUT_S = 10.0


@pytest.fixture(autouse=True, params=["per-directory", "recursive"])
def watching(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Every test here against both placements. Off Linux only the recursive
    one exists; on Linux it is the one macOS, Windows and the fallback use."""
    if request.param == "per-directory" and not sys.platform.startswith("linux"):
        pytest.skip("per-directory watches are Linux only")
    if request.param == "recursive":
        monkeypatch.setattr(watcher_module.platform, "is_linux", lambda: False)
    return request.param


def test_a_flow_watches_its_own_cells_and_its_workspaces_shared_code(tmp_path: Path):
    root = tmp_path / "project"
    flow = root / "churn.flow"
    (root / "ignored").mkdir(parents=True)
    (root / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    environment = root / "custom-environment"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("home = /python\n", encoding="utf-8")
    watch = WatchSet(flow_dir=flow, workspace_dir=root)

    seen = {
        "cell": watch.classify(flow / "cells" / "score.py"),
        "nested": watch.classify(flow / "cells" / "old" / "score.py"),
        "neighbour": watch.classify(root / "sales.flow" / "cells" / "score.py"),
        "stray": watch.classify(flow / "util.py"),
        "helper": watch.classify(root / "helpers.py"),
        "nested_helper": watch.classify(root / "lib" / "helpers.py"),
        "data": watch.classify(root / "data" / "raw.csv"),
        "store": watch.classify(store_dir(flow) / "kernel" / "scratch.py"),
        "venv": watch.classify(root / ".venv" / "lib" / "site.py"),
        "named_venv": watch.classify(root / "venv" / "lib" / "site.py"),
        "site_packages": watch.classify(
            root / "lib" / "site-packages" / "installed.py"
        ),
        "marked_venv": watch.classify(environment / "installed.py"),
        "gitignored": watch.classify(root / "ignored" / "generated.py"),
        "cache": watch.classify(root / "__pycache__" / "helpers.py"),
        "outside": watch.classify(tmp_path / "elsewhere.py"),
    }

    assert seen == {
        "cell": "cell",
        "nested": None,
        "neighbour": None,
        "stray": "code",
        "helper": "code",
        "nested_helper": "code",
        "data": None,
        "store": None,
        "venv": None,
        "named_venv": None,
        "site_packages": None,
        "marked_venv": None,
        "gitignored": None,
        "cache": None,
        "outside": None,
    }
    assert watch.root == root


async def test_nested_flows_hold_their_containing_directories_as_watch_roots(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", flows=("a",))
    inner = make_workspace(root / "exp", flows=("b",))

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "a"})
        await api.flow_open({"flow": "exp/b"})
        outer_session = api.hub.session("a")
        inner_session = api.hub.session("b")

        assert outer_session.workspace_dir == root
        assert inner_session.workspace_dir == inner
        assert api.hub.watches.roots() == [root, inner]
        assert outer_session.watch.classify(inner / "helpers.py") == "code"
        assert inner_session.watch.classify(inner / "helpers.py") == "code"
        assert outer_session.watch.classify(root / "top.py") == "code"
        assert inner_session.watch.classify(root / "top.py") is None

        await api.flow_delete({"flow": "b"})
        assert api.hub.watches.roots() == [root]


def test_an_outside_flow_watches_its_own_workspace_not_the_launch_one(tmp_path: Path):
    launch = tmp_path / "project"
    elsewhere = tmp_path / "elsewhere"
    flow = elsewhere / "other.flow"
    watch = WatchSet(flow_dir=flow, workspace_dir=elsewhere)

    seen = {
        "own_cell": watch.classify(flow / "cells" / "score.py"),
        "own_helper": watch.classify(elsewhere / "helpers.py"),
        "launch_helper": watch.classify(launch / "helpers.py"),
        "launch_cell": watch.classify(launch / "churn.flow" / "cells" / "score.py"),
    }

    assert seen == {
        "own_cell": "cell",
        "own_helper": "code",
        "launch_helper": None,
        "launch_cell": None,
    }
    assert watch.root == elsewhere


def test_flows_in_one_workspace_share_its_watch(tmp_path: Path):
    root = tmp_path / "project"
    elsewhere = tmp_path / "elsewhere"
    watches = Watches()
    scheduled: list[Path] = []
    dropped: list[Path] = []
    watches.observe = scheduled.append
    watches.forget = dropped.append

    watches.hold(root)
    watches.hold(root)
    watches.hold(elsewhere)
    after_open = list(watches.roots())
    watches.release(root)
    still_held = list(watches.roots())
    watches.release(root)
    watches.release(elsewhere)

    assert scheduled == [root, elsewhere]
    assert after_open == sorted([elsewhere, root])
    assert still_held == sorted([elsewhere, root])
    assert dropped == [root, elsewhere]
    assert watches.roots() == []


async def test_a_second_flow_in_the_workspace_adds_no_second_watch(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    outside = _outside_flow(tmp_path / "elsewhere")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            await api.flow_open({"flow": "sales"})
            shared = list(api.hub.watches.roots())
            await api.flow_open({"flow": str(outside)})
            reached = list(api.hub.watches.roots())
        finally:
            await watcher.stop()

    assert shared == [root]
    assert reached == sorted([root, outside.parent])


async def test_an_edit_to_one_flow_leaves_its_neighbour_alone(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})
        churn, sales = await opened(api, "churn"), await opened(api, "sales")
        before = len(transactions(sales))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_cell(root / "churn.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: "0.93" in _stored(churn))
        finally:
            await watcher.stop()
        untouched = len(transactions(sales)) == before

    assert untouched


async def test_a_data_file_nobody_declared_wakes_nobody(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    for name in FLOWS:
        write_cell(root / f"{name}.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})
        sessions = [await opened(api, name) for name in FLOWS]
        before = [len(transactions(session)) for session in sessions]
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_file(root / "raw.csv", "id,label\n1,0\n")
            write_file(root / "notes.txt", "nothing to do with any flow")
            await asyncio.sleep(_DEBOUNCE_S * 10)
            await watcher.flush()
        finally:
            await watcher.stop()
        after = [len(transactions(session)) for session in sessions]

    assert after == before


async def test_a_broken_flow_yaml_does_not_cost_its_neighbour_its_wake(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    for name in FLOWS:
        write_cell(root / f"{name}.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})
        await opened(api, "churn")
        sales = await opened(api, "sales")
        watcher = Watcher(api.hub, debounce_s=600)
        write_file(
            manifest_path(root / "churn.flow"),
            "<<<<<<< HEAD\nname: churn\n=======\nname: other\n>>>>>>> theirs\n",
        )
        write_cell(root / "churn.flow", "score", SCORE_CELL.replace("0.91", "0.92"))
        write_cell(root / "sales.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
        for name in FLOWS:
            watcher.notice(root / f"{name}.flow" / "cells" / "score.py")
        await watcher.flush()
        await watcher.stop()
        observed = _stored(sales)

    assert "0.93" in observed


async def test_a_flow_nobody_opened_is_not_opened_by_an_event(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_cell(root / "sales.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
            await asyncio.sleep(_DEBOUNCE_S * 10)
            await watcher.flush()
        finally:
            await watcher.stop()
        attached = sorted(session.ref.name for session in api.hub.opened())

    assert attached == ["churn"]


async def test_an_outside_flows_own_cell_edit_reaches_its_session(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    outside = _outside_flow(tmp_path / "elsewhere")
    write_cell(outside, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": str(outside)})
        session = api.hub.attached(outside)
        assert session is not None
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_cell(outside, "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: "0.93" in _stored(session))
        finally:
            await watcher.stop()
        observed = _stored(session)

    assert "0.93" in observed


async def test_an_outside_flow_takes_its_own_helpers_and_not_the_launch_ones(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", files={"helpers.py": "AUC = 1"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    outside = _outside_flow(tmp_path / "elsewhere", files={"helpers.py": "AUC = 1"})
    write_cell(outside, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.flow_open({"flow": str(outside)})
        session = api.hub.attached(outside)
        assert session is not None
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_file(root / "helpers.py", "AUC = 2")
            await _until(lambda: _code_changes(api, "churn") == [["helpers.py"]])
            left_alone = _tree_changes(session)
            write_file(outside.parent / "helpers.py", "AUC = 3")
            await _until(lambda: _tree_changes(session) == [["helpers.py"]])
        finally:
            await watcher.stop()

    assert left_alone == []


async def test_an_edit_burst_lands_as_one_transaction_once_it_quiets(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = len(transactions(session))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            for slug in ("alpha", "beta", "gamma"):
                write_cell(flow, slug, SCORE_CELL.replace("Score", slug.title()))
                watcher.notice(flow / "cells" / f"{slug}.py")
            during = len(transactions(session))
            await _until(lambda: len(transactions(session)) > before)
        finally:
            await watcher.stop()
        landed = transactions(session)[before:]
        accepted = sorted(slice_of(session, "main"))

    assert during == before
    assert len(landed) == 1
    assert landed[0].intent == "added alpha; added beta; added gamma"
    assert accepted == ["alpha", "beta", "gamma", "score"]


async def test_a_real_event_reaches_the_store_without_anyone_asking(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: "0.93" in _stored(session))
        finally:
            await watcher.stop()
        observed = _stored(session)

    assert "0.93" in observed


async def test_a_watched_helper_edit_reaches_every_flow_in_the_workspace(
    tmp_path: Path,
):
    root = make_workspace(
        tmp_path / "project", flows=("churn", "sales"), files={"helpers.py": "AUC = 1"}
    )
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        for name in FLOWS:
            await api.flow_open({"flow": name, "worktree": False})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_file(root / "helpers.py", "AUC = 2")
            await _until(lambda: all(_code_changes(api, name) for name in FLOWS))
        finally:
            await watcher.stop()
        changes = {name: _code_changes(api, name) for name in FLOWS}

    assert changes == {"churn": [["helpers.py"]], "sales": [["helpers.py"]]}


async def test_a_watched_edit_during_an_agent_session_is_flagged_uncertain(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        session = api.hub.session("churn")
        before = len(transactions(session))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: len(transactions(session)) > before)
        finally:
            await watcher.stop()
        landed = transactions(session)[-1]

    assert landed.actor == "claude-1"
    assert [op.detail for op in landed.ops if isinstance(op, FlagSet)] == [
        "attribution uncertain. two authors edited in one window"
    ]
    assert [op.flag for op in landed.ops if isinstance(op, FlagSet)] == [MIXED_EDITING]


async def test_a_watched_edit_with_two_registered_agents_belongs_to_user(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        await api.agent_begin({"flow": "churn", "label": "codex-2"})
        session = api.hub.session("churn")
        before = len(transactions(session))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: len(transactions(session)) > before)
        finally:
            await watcher.stop()
        landed = transactions(session)[-1]

    assert landed.actor == "user"


async def test_reading_the_workspace_wakes_nobody(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = _CountingWatcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            for path in sorted(root.rglob("*.py")):
                path.read_bytes()
            await _barrier(watcher, root)
        finally:
            await watcher.stop()

    assert (watcher.flushes, watcher.woken) == (0, set())


async def test_a_scan_does_not_wake_the_next_scan(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        watcher = _CountingWatcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            await api.hub.quiesce(session)
            await _barrier(watcher, root)
        finally:
            await watcher.stop()

    assert (watcher.flushes, watcher.woken) == (0, set())


async def test_a_write_wakes_exactly_one_flush(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = _CountingWatcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_file(root / "helpers.py", "AUC = 2")
            await _until(lambda: watcher.flushes == 1 and _settled(watcher))
            await _barrier(watcher, root)
        finally:
            await watcher.stop()

    assert (watcher.flushes, watcher.woken) == (1, set())


async def test_an_edit_during_a_scan_brings_exactly_one_more_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    entered, release = threading.Event(), threading.Event()
    scans: list[Path] = []

    def held_scan(workspace_dir: Path, **kwargs: Any) -> WorkspaceTree:
        scans.append(workspace_dir)
        entered.set()
        release.wait(_DELIVERY_TIMEOUT_S)
        return scan_workspace(workspace_dir, **kwargs)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = _CountingWatcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        monkeypatch.setattr(hub_module, "scan_workspace", held_scan)
        try:
            write_file(root / "helpers.py", "AUC = 2")
            assert await asyncio.to_thread(entered.wait, _DELIVERY_TIMEOUT_S)
            write_file(root / "helpers.py", "AUC = 3")
            write_file(root / "lib/io.py", "N = 2")
            await _barrier(watcher, root, settled=False)
            release.set()
            await _until(lambda: len(scans) == 2 and _settled(watcher))
            await _barrier(watcher, root)
        finally:
            release.set()
            await watcher.stop()
        changes = _code_changes(api, "churn")

    assert (len(scans), watcher.flushes) == (2, 2)
    assert changes == [["helpers.py", "lib/io.py"]]


async def test_an_edit_inside_an_excluded_directory_wakes_nobody(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    for excluded in ("node_modules/pkg", ".venv/lib", ".git/hooks"):
        (root / excluded).mkdir(parents=True)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = _CountingWatcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            for excluded in ("node_modules/pkg", ".venv/lib", ".git/hooks"):
                write_file(root / excluded / "module.py", "X = 1")
            await _barrier(watcher, root)
        finally:
            await watcher.stop()

    assert (watcher.flushes, watcher.woken) == (0, set())


async def test_a_helper_in_a_directory_made_after_the_watch_wakes_the_flow(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            write_file(root / "features" / "fresh" / "scaling.py", "S = 1")
            await _until(
                lambda: _code_changes(api, "churn") == [["features/fresh/scaling.py"]]
            )
        finally:
            await watcher.stop()


@pytest.mark.parametrize("away", ["node_modules", "../outside"])
async def test_moving_a_directory_away_and_back_reaches_the_tree(
    tmp_path: Path, away: str
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    moved = {"lib/io.py", "lib/metrics.py"}

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        try:
            (root / "lib").rename(root / away)
            await _until(lambda: not moved & _tree_files(session))
            (root / away).rename(root / "lib")
            await _until(lambda: moved <= _tree_files(session))
        finally:
            await watcher.stop()


async def test_a_vanished_directory_wakes_the_flows_that_scanned_files_below_it(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_file(root / "raw.csv", "id\n1\n")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        watcher = Watcher(api.hub, debounce_s=600)
        (root / "raw.csv").unlink()
        watcher.vanished(root / "raw.csv")
        data_woke = set(watcher._woken)
        (root / "lib").rename(tmp_path / "outside")
        watcher.vanished(root / "lib")
        await watcher.flush()
        await watcher.stop()
        left = _tree_files(session)

    assert data_woke == set()
    assert not {"lib/io.py", "lib/metrics.py"} & left


async def test_an_open_does_not_wait_for_another_workspaces_watch(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)
    outside = _outside_flow(tmp_path / "elsewhere")

    async with daemon_api(root) as api:
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        held = _HeldPlacement(watcher, root)
        try:
            slow = asyncio.create_task(api.flow_open({"flow": "churn"}))
            await asyncio.to_thread(held.entered.wait, _DELIVERY_TIMEOUT_S)
            await asyncio.wait_for(
                api.flow_open({"flow": str(outside)}), _DELIVERY_TIMEOUT_S
            )
            waited = not slow.done()
            held.release.set()
            await asyncio.wait_for(slow, _DELIVERY_TIMEOUT_S)
        finally:
            held.release.set()
            await watcher.stop()

    assert waited


async def test_stopping_the_watcher_mid_placement_ends_the_wait(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", files=_HELPERS)

    async with daemon_api(root) as api:
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        await watcher.start()
        held = _HeldPlacement(watcher, root)
        slow = asyncio.create_task(api.flow_open({"flow": "churn"}))
        await asyncio.to_thread(held.entered.wait, _DELIVERY_TIMEOUT_S)

        await asyncio.wait_for(watcher.stop(), _DELIVERY_TIMEOUT_S)
        await asyncio.wait_for(slow, _DELIVERY_TIMEOUT_S)


class _HeldPlacement:
    """Holds the placement of `root`'s watch, the way a walk of a very large
    tree would, until released or the watcher stops."""

    def __init__(self, watcher: Watcher, root: Path) -> None:
        placement = watcher._placement
        assert placement is not None
        schedule = placement.schedule
        self.entered, self.release = threading.Event(), threading.Event()

        def held(scheduled: Path) -> None:
            if scheduled == root:
                self.entered.set()
                while not self.release.wait(0.01):
                    if watcher._stopping.is_set():
                        return
            schedule(scheduled)

        placement.schedule = held  # type: ignore[method-assign]


def _tree_files(session: FlowSession) -> set[str]:
    tree = session.store.index.workspace_tree()
    return set(tree.files) if tree else set()


FLOWS = ("churn", "sales")
_HELPERS = {"helpers.py": "AUC = 1", "lib/metrics.py": "K = 3", "lib/io.py": "N = 1"}


class _CountingWatcher(Watcher):
    def __init__(self, hub: Hub, *, debounce_s: float) -> None:
        super().__init__(hub, debounce_s=debounce_s)
        self.flushes = 0
        self.noticed: set[Path] = set()

    @property
    def woken(self) -> set[Path]:
        return set(self._woken)

    def notice(self, path: Path) -> None:
        self.noticed.add(path.resolve())
        super().notice(path)

    async def flush(self) -> None:
        self.flushes += 1
        await super().flush()


def _settled(watcher: Watcher) -> bool:
    return watcher._timer is None or watcher._timer.done()


async def _barrier(
    watcher: _CountingWatcher, root: Path, *, settled: bool = True
) -> None:
    """Wait until an event written now has been noticed: inotify delivers in
    order, so everything the steps before it caused has been noticed too."""
    marker = write_file(root / f"barrier-{len(watcher.noticed)}.txt", "-")
    await _until(
        lambda: (
            marker.resolve() in watcher.noticed and (not settled or _settled(watcher))
        )
    )


def _outside_flow(
    directory: Path, *, name: str = "other", files: dict[str, str] | None = None
) -> Path:
    make_workspace(directory, flows=(name,), files=files)
    return directory / f"{name}.flow"


def _code_changes(api: Api, flow: str) -> list[list[str]]:
    return _tree_changes(api.hub.session(flow))


def _tree_changes(session: FlowSession) -> list[list[str]]:
    tree = session.store.index.workspace_tree()
    return [tree.changed_paths] if tree and tree.changed_paths else []


def _stored(session: FlowSession) -> str:
    version = slice_of(session, "main")["score"]
    return session.store.objects.get(version.raw_source_ref).decode("utf-8")


async def _until(
    ready: Callable[[], bool], timeout: float = _DELIVERY_TIMEOUT_S
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if ready():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the watcher never got there")
