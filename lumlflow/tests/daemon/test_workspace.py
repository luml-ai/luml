import json
import os
import sys
from pathlib import Path

import pytest
from lumlflow import __version__
from lumlflow.flow.daemon import workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowAmbiguous, FlowError, FlowNotFound
from lumlflow.flow.store.flowstore import CELLS_DIRNAME

from tests.daemon.helpers import make_workspace


def test_a_listing_reads_one_level_and_never_descends(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    make_workspace(root / "experiments", flows=("sweep",))
    (root / ".venv" / "hidden.flow").mkdir(parents=True)
    (root / "node_modules").mkdir()
    (root / ".git").mkdir()
    (root / "notes.txt").write_text("")

    listing = workspace.list_directory(root)

    assert [flow.relpath for flow in listing.flows] == ["churn.flow"]
    assert listing.folders == [root / "experiments"]


def test_a_listing_of_a_missing_directory_is_refused(tmp_path: Path):
    with pytest.raises(FlowError):
        workspace.list_directory(tmp_path / "nowhere")


def test_flow_selection_answers_or_names_the_candidates(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))

    assert workspace.select_flow(root, name="churn").name == "churn"
    assert workspace.select_flow(root, name="sales.flow").name == "sales"
    assert (
        workspace.select_flow(root, cwd=root / "sales.flow" / CELLS_DIRNAME).name
        == "sales"
    )
    with pytest.raises(FlowAmbiguous) as ambiguous:
        workspace.select_flow(root, cwd=root)
    assert "`churn`" in str(ambiguous.value) and "`sales`" in str(ambiguous.value)


def test_a_bare_name_of_nested_flows_is_told_to_use_a_path(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())
    make_workspace(root / "a", flows=("sales",))
    make_workspace(root / "b", flows=("sales",))

    with pytest.raises(FlowNotFound) as missing:
        workspace.select_flow(root, name="sales")

    assert "by its path, like `a/sales`" in str(missing.value)


def test_a_single_flow_workspace_needs_no_flow_argument(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    assert workspace.select_flow(root, cwd=root).name == "churn"


def test_a_caller_standing_inside_a_flow_needs_no_search_root(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    cells = root / "churn.flow" / CELLS_DIRNAME

    assert workspace.select_flow(cells).path == root / "churn.flow"
    assert workspace.select_flow(cells, name="churn").path == root / "churn.flow"


def test_an_unknown_flow_name_lists_what_there_is(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))

    with pytest.raises(FlowNotFound) as missing:
        workspace.select_flow(root, name="sweep")

    assert "`sweep`" in str(missing.value) and "`churn`" in str(missing.value)


def test_a_flow_outside_the_workspace_is_addressed_by_its_own_path(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    outside = make_workspace(tmp_path / "other", flows=("sales",)) / "sales.flow"

    ref = workspace.select_flow(root, name=str(outside))

    assert (ref.name, ref.path) == ("sales", outside)
    assert ref.relpath == outside.as_posix()
    assert workspace.select_flow(root, name=str(root / "churn.flow")).relpath == (
        "churn.flow"
    )
    with pytest.raises(FlowNotFound):
        workspace.select_flow(root, name=str(tmp_path / "other"))
    with pytest.raises(FlowNotFound):
        workspace.select_flow(root, name=str(tmp_path / "nowhere.flow"))


def _no_listing(root: Path) -> workspace.DirectoryListing:
    raise AssertionError(f"`{root}` was listed")


def test_an_absolute_path_inside_a_wide_root_is_addressed_without_listing(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "home", flows=())
    flow = make_workspace(root / "work" / "ml", flows=("churn",)) / "churn.flow"

    ref = workspace.select_flow(root, name=str(flow), lister=_no_listing)

    assert (ref.name, ref.path, ref.relpath) == ("churn", flow, "work/ml/churn.flow")


def test_a_nested_flow_is_addressed_by_its_relative_path(tmp_path: Path):
    root = make_workspace(tmp_path / "home", flows=())
    flow = make_workspace(root / "work" / "ml", flows=("churn",)) / "churn.flow"

    by_path = workspace.select_flow(root, name="work/ml/churn", lister=_no_listing)
    suffixed = workspace.select_flow(root, name="work/ml/churn.flow")

    assert (by_path.name, by_path.path, by_path.relpath) == (
        "churn",
        flow,
        "work/ml/churn.flow",
    )
    assert suffixed == by_path
    with pytest.raises(FlowNotFound):
        workspace.select_flow(root, name="work/ml/sales")


def test_a_bare_name_of_a_deep_flow_is_told_to_use_its_path(tmp_path: Path):
    root = make_workspace(tmp_path / "home", flows=("sales",))
    make_workspace(root / "work" / "ml", flows=("churn",))

    with pytest.raises(FlowNotFound) as missing:
        workspace.select_flow(root, name="churn")

    message = str(missing.value)
    assert "`churn`" in message and "`sales`" in message
    assert "by its path" in message and "`work/churn`" in message


def test_a_flow_inside_another_flow_is_refused_by_any_path(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())
    nested = make_workspace(root / "outer.flow", flows=("inner",)) / "inner.flow"

    for name in (str(nested), "outer.flow/inner", "outer/inner"):
        with pytest.raises(FlowNotFound):
            workspace.select_flow(root, name=name)


def test_a_folder_a_listing_hides_is_still_reached_by_its_path(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())
    built = make_workspace(root / "build", flows=("churn",)) / "churn.flow"
    hidden = make_workspace(root / "node_modules" / "pkg", flows=("x",)) / "x.flow"

    assert workspace.select_flow(root, name="build/churn").path == built
    assert workspace.select_flow(root, name=str(hidden)).path == hidden
    assert workspace.list_directory(root).folders == []


def test_a_relative_name_may_not_climb_out_of_the_directory(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())
    make_workspace(tmp_path / "other", flows=("churn",))

    with pytest.raises(FlowError):
        workspace.select_flow(root, name="../other/churn")


@pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0, reason="needs unix permissions"
)
def test_a_listing_of_an_unreadable_directory_is_refused(tmp_path: Path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        with pytest.raises(FlowError) as refused:
            workspace.list_directory(locked)
    finally:
        locked.chmod(0o700)

    assert "cannot read" in str(refused.value)


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
def test_a_linked_flow_is_listed_at_its_target(tmp_path: Path):
    target = make_workspace(tmp_path / "elsewhere", flows=("churn",)) / "churn.flow"
    root = make_workspace(tmp_path / "project", flows=())
    (root / "linked.flow").symlink_to(target)

    (flow,) = workspace.list_directory(root).flows

    assert (flow.name, flow.path, flow.relpath) == ("linked", target, "linked.flow")


def test_a_listing_of_a_flow_is_that_flow(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    (root / "churn.flow" / "notes").mkdir()

    listing = workspace.list_directory(root / "churn.flow")

    assert [(flow.name, flow.path, flow.relpath) for flow in listing.flows] == [
        ("churn", root / "churn.flow", ".")
    ]
    assert listing.folders == []


def test_only_the_daemon_instance_that_registered_clears_the_record() -> None:
    record = _record("first")
    workspace.write_record(record)

    workspace.clear_record(instance_id="successor")
    assert workspace.read_record() == record

    workspace.clear_record(instance_id=record.instance_id)
    assert workspace.read_record() is None


def test_the_daemon_uses_one_unkeyed_record() -> None:
    record = _record("singleton")

    assert workspace.record_path() == workspace.state_dir() / workspace.RECORD_NAME
    assert workspace.log_path() == (
        workspace.state_dir() / workspace.LOGS_DIRNAME / workspace.LOG_NAME
    )
    workspace.write_record(record)

    assert workspace.read_record() == record
    assert set(json.loads(workspace.record_path().read_text())) == {
        "instance_id",
        "pid",
        "port",
        "token",
        "tracker_store",
        "version",
        "web_host",
        "web_port",
    }


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX modes there")
def test_the_daemon_record_is_private() -> None:
    workspace.write_record(_record("private"))

    assert workspace.record_path().stat().st_mode & 0o777 == 0o600


def _record(instance_id: str) -> DaemonRecord:
    return DaemonRecord(
        pid=os.getpid(),
        instance_id=instance_id,
        port=1234,
        token="token",
        web_host="127.0.0.1",
        web_port=5000,
        tracker_store="/tmp/experiments",
        version=__version__,
    )
