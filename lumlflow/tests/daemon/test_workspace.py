"""Which directory is the workspace, which flow a verb means, what a browser
sees, and who holds the daemon record."""

import json
import os
import sys
from pathlib import Path

import pytest
from lumlflow import __version__
from lumlflow.flow.daemon import workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowAmbiguous, FlowNotFound
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, STORE_DIRNAME

from tests.daemon.helpers import make_workspace


def test_flows_are_found_nested_and_never_descended_into(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))
    make_workspace(root / "experiments", flows=("sweep",))
    (root / ".venv" / "hidden.flow").mkdir(parents=True)
    (root / "churn.flow" / STORE_DIRNAME / "worktrees" / "inner.flow").mkdir(
        parents=True
    )

    found = {flow.relpath for flow in workspace.find_flows(root)}

    assert found == {"churn.flow", "experiments/sweep.flow"}


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


def test_a_bare_duplicate_name_is_refused_with_both_absolute_paths(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())
    first = make_workspace(root / "a", flows=("sales",)) / "sales.flow"
    second = make_workspace(root / "b", flows=("sales",)) / "sales.flow"

    with pytest.raises(FlowAmbiguous) as ambiguous:
        workspace.select_flow(root, name="sales")

    assert str(first) in str(ambiguous.value)
    assert str(second) in str(ambiguous.value)


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
    # A flow the workspace does contain is the flow it already was, however it
    # is spelled — no second identity for one directory.
    assert workspace.select_flow(root, name=str(root / "churn.flow")).relpath == (
        "churn.flow"
    )
    with pytest.raises(FlowNotFound):
        workspace.select_flow(root, name=str(tmp_path / "other"))
    with pytest.raises(FlowNotFound):
        workspace.select_flow(root, name=str(tmp_path / "nowhere.flow"))


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
