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
        await api.flow_open({"flow": "b"})
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
            await asyncio.sleep(_DEBOUNCE_S * 10)
            await watcher.flush()
        finally:
            await watcher.stop()
        after = [len(transactions(session)) for session in sessions]

    assert after == before


async def test_a_flow_nobody_opened_is_not_opened_by_an_event(tmp_path: Path):
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
        watcher.start()
        try:
            write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.93"))
            await _until(lambda: len(transactions(session)) > before)
        finally:
            await watcher.stop()
        landed = transactions(session)[-1]

    assert landed.actor == "user"


FLOWS = ("churn", "sales")


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
