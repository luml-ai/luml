"""The watcher: what one flow looks at, how it groups, and that it is never the
thing correctness rests on.

The observer runs for real here — an event delivered by the platform is the
only honest way to test wiring that exists to receive them — but every
assertion is about what the store ends up holding, never about the event.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path

from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import FlowSession
from lumlflow.flow.daemon.reconcile import MIXED_EDITING
from lumlflow.flow.daemon.watcher import Watcher, Watches, WatchSet
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.flow.store.models import FlagSet

from tests.daemon.helpers import (
    SCORE_CELL,
    daemon_api,
    make_workspace,
    slice_of,
    transactions,
    write_cell,
    write_file,
)

_DEBOUNCE_S = 0.05
_DELIVERY_TIMEOUT_S = 10.0


def test_a_flow_watches_its_own_cells_and_its_workspaces_shared_code(tmp_path: Path):
    """Classification is by directory, never by shape: this flow's `cells/`
    holds its cells, every other watched `.py` under its workspace is shared
    code, and data files are not watched at all — the store never versions them,
    and a run that reads one is `external` and never memoized.

    A neighbour flow's cell file is neither: it is that flow's news, and
    `scan_workspace` cuts every `cells/` out of the shared-code tree.
    """
    root = tmp_path / "project"
    flow = root / "churn.flow"
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
        "cache": watch.classify(root / "__pycache__" / "helpers.py"),
        "outside": watch.classify(tmp_path / "elsewhere.py"),
    }

    assert seen == {
        "cell": "cell",
        # Acceptance globs `cells/*.py`, so nothing deeper is a cell — and the
        # shared-code scan prunes the whole `cells/` subtree, so it is not that
        # either.
        "nested": None,
        "neighbour": None,
        # A stray module inside a flow is shared code, not a cell.
        "stray": "code",
        "helper": "code",
        "nested_helper": "code",
        "data": None,
        "store": None,
        "venv": None,
        "cache": None,
        "outside": None,
    }
    assert watch.root == root


def test_an_outside_flow_watches_its_own_workspace_not_the_launch_one(tmp_path: Path):
    """A flow opened by absolute path runs under its own environment and its own
    helpers, so it watches those — the launch directory's shared code is not
    code it can import."""
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
    """Refcounted, so two sessions over one tree schedule one observer — and the
    last one to close is what takes it back down."""
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
    """One tree, one watch, however many flows are open on it — and the flow
    from outside brings its own, which is the tree nothing reached before."""
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    outside = _outside_flow(tmp_path / "elsewhere")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
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
    """Not every workspace change is a given flow's news. A cell file is one
    flow's plane, and the flow beside it must not so much as reconcile."""
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})
        churn, sales = api.hub.session("churn"), api.hub.session("sales")
        before = len(transactions(sales))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
        try:
            write_cell(root / "churn.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: "0.93" in _stored(churn))
        finally:
            await watcher.stop()
        untouched = len(transactions(sales)) == before

    assert untouched


async def test_a_data_file_nobody_declared_wakes_nobody(tmp_path: Path):
    """Data is reached through `ctx.workspace_dir` and marks the run `external`,
    which is never memoized — so there is nothing an event over one invalidates,
    and waking a flow for it would be a reconciliation with no cause."""
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    for name in FLOWS:
        write_cell(root / f"{name}.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})
        sessions = [api.hub.session(name) for name in FLOWS]
        before = [len(transactions(session)) for session in sessions]
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
        try:
            write_file(root / "raw.csv", "id,label\n1,0\n")
            write_file(root / "notes.txt", "nothing to do with any flow")
            # The debounce cannot have elapsed before the events would have,
            # and a flush that never armed leaves the journals where they were.
            await asyncio.sleep(_DEBOUNCE_S * 10)
            await watcher.flush()
        finally:
            await watcher.stop()
        after = [len(transactions(session)) for session in sessions]

    assert after == before


async def test_a_flow_nobody_opened_is_not_opened_by_an_event(tmp_path: Path):
    """Waking is for a session somebody is watching. A flow nobody attached to
    has none, and whatever moved under it is the cold-start tier's to take up
    when someone opens it."""
    root = make_workspace(tmp_path / "project", flows=FLOWS)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
        try:
            write_cell(root / "sales.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
            await asyncio.sleep(_DEBOUNCE_S * 10)
            await watcher.flush()
        finally:
            await watcher.stop()
        attached = sorted(session.ref.name for session in api.hub.opened())

    assert attached == ["churn"]


async def test_an_outside_flows_own_cell_edit_reaches_its_session(tmp_path: Path):
    """The flow the launch directory does not contain is watched over its own
    workspace, which is where its cells and its helpers both are."""
    root = make_workspace(tmp_path / "project")
    outside = _outside_flow(tmp_path / "elsewhere")
    write_cell(outside, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": str(outside)})
        session = api.hub.attached(outside)
        assert session is not None
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
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
    """It runs under its own environment, so it is its own workspace's shared
    code that changes its cells' behaviour — and the launch workspace's helper
    is a file it cannot import."""
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
        watcher.start()
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
    """A debounce is what keeps an agent writing four files from becoming four
    journal lines nobody can read as one act."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        before = len(transactions(session))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
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
        watcher.start()
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
    """Shared code is workspace-scoped, so its transition is appended to each
    flow's own journal — a flow has to rebuild standalone from its own."""
    root = make_workspace(
        tmp_path / "project", flows=("churn", "sales"), files={"helpers.py": "AUC = 1"}
    )
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.status({})
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
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
    """One shared worktree cannot tell an agent's write from the human's, so
    the window is flagged rather than the name being claimed."""
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.agent_begin({"flow": "churn", "label": "claude-1"})
        session = api.hub.session("churn")
        before = len(transactions(session))
        watcher = Watcher(api.hub, debounce_s=_DEBOUNCE_S)
        watcher.start()
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


FLOWS = ("churn", "sales")


def _outside_flow(
    directory: Path, *, name: str = "other", files: dict[str, str] | None = None
) -> Path:
    """A flow in a workspace of its own, above the launch directory."""
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
    """Wait for the watcher to have done its work, or give up loudly."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if ready():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("the watcher never got there")
