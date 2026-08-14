"""Which directory is the workspace, which flow a verb means, what a browser
sees, and who holds the daemon record."""

import os
import sys
from pathlib import Path

import pytest
from lumlflow.flow.daemon import workspace
from lumlflow.flow.errors import FlowAmbiguous, FlowNotFound
from lumlflow.flow.store.flowstore import CELLS_DIRNAME, STORE_DIRNAME

from tests.daemon.helpers import make_workspace, write_file


def test_the_workspace_is_the_nearest_ancestor_holding_a_flow(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    inside = root / "churn.flow" / CELLS_DIRNAME

    assert workspace.resolve_root(inside) == root
    assert workspace.resolve_root(root / "churn.flow") == root


def test_a_directory_with_no_flow_is_its_own_workspace(tmp_path: Path):
    bare = tmp_path / "empty"
    bare.mkdir()

    assert workspace.resolve_root(bare) == bare


def test_a_registered_ancestor_is_the_workspace_even_without_a_flow(tmp_path: Path):
    root = tmp_path / "registered"
    (root / "notes").mkdir(parents=True)
    workspace.write_record(workspace.new_record(root, port=1, token="t"))

    assert workspace.resolve_root(root / "notes") == root


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


def test_a_single_flow_workspace_needs_no_flow_argument(tmp_path: Path):
    root = make_workspace(tmp_path / "project")

    assert workspace.select_flow(root, cwd=root).name == "churn"


def test_an_unknown_flow_name_lists_what_there_is(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))

    with pytest.raises(FlowNotFound) as missing:
        workspace.select_flow(root, name="sweep")

    assert "`sweep`" in str(missing.value) and "`churn`" in str(missing.value)


def test_the_browser_lists_a_flow_as_one_entry(tmp_path: Path):
    root = make_workspace(
        tmp_path / "project",
        files={"helpers.py": "VALUE = 1", "data/raw.csv": "a,b"},
    )
    write_file(root / "churn.flow" / CELLS_DIRNAME / "score.py", "class Score: pass")

    entries = workspace.listing(root)["entries"]

    assert [(entry["name"], entry["kind"]) for entry in entries] == [
        ("churn.flow", "flow"),
        ("data", "dir"),
        ("helpers.py", "file"),
    ]
    assert next(entry for entry in entries if entry["kind"] == "file")["size"] == len(
        b"VALUE = 1\n"
    )


def test_the_browser_never_opens_a_flow(tmp_path: Path):
    root = make_workspace(tmp_path / "project", files={"notes/todo.md": "later"})
    (root / "churn.flow" / STORE_DIRNAME).mkdir(parents=True, exist_ok=True)

    assert workspace.listing(root, "notes")["path"] == "notes"
    with pytest.raises(FlowNotFound) as refused:
        workspace.listing(root, "churn.flow")
    with pytest.raises(FlowNotFound):
        workspace.listing(root, f"churn.flow/{CELLS_DIRNAME}")
    with pytest.raises(FlowNotFound):
        workspace.listing(root, str(root / "churn.flow" / CELLS_DIRNAME))

    assert "open it rather than browsing it" in str(refused.value)


def test_the_browser_climbs_above_the_launch_directory(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    make_workspace(tmp_path / "other", flows=("sales",))
    write_file(tmp_path / "outside.txt", "context")

    here = workspace.listing(root)
    above = workspace.listing(root, here["parent"])

    assert here["outside"] is False
    assert here["path"] == "" and here["parent"] == str(tmp_path)
    assert above["outside"] is True
    # The launch directory is still what `root` names; only the listing moved.
    assert above["root"] == str(root) and above["path"] == str(tmp_path)
    assert [(entry["name"], entry["kind"]) for entry in above["entries"]] == [
        ("other", "dir"),
        ("project", "dir"),
        ("outside.txt", "file"),
    ]
    # Above the workspace an entry spells itself absolutely — there is no
    # root-relative name for a directory the workspace does not contain.
    assert [entry["path"] for entry in above["entries"]] == [
        str(tmp_path / "other"),
        str(root),
        str(tmp_path / "outside.txt"),
    ]


def test_climbing_back_down_reaches_a_flow_in_another_directory(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    make_workspace(tmp_path / "other", flows=("sales",))

    sideways = workspace.listing(root, str(tmp_path / "other"))

    assert sideways["outside"] is True
    assert ("sales.flow", "flow") in [
        (entry["name"], entry["kind"]) for entry in sideways["entries"]
    ]
    # And walking back down into the workspace is the workspace again, spelled
    # the way every existing caller spells it.
    assert workspace.listing(root, str(root))["path"] == ""
    assert workspace.listing(root, str(root))["outside"] is False


def test_the_filesystem_root_is_where_climbing_stops(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    top = Path(tmp_path.anchor)

    assert workspace.listing(root, str(top))["parent"] is None


@pytest.mark.skipif(sys.platform == "win32", reason="no POSIX modes there")
@pytest.mark.skipif(os.geteuid() == 0, reason="root reads everything")
def test_a_directory_nobody_may_read_is_a_refusal_and_not_a_traceback(tmp_path: Path):
    """Climbing meets directories the user does not own — `/root`, another
    account's home. That is a sentence the browser prints, not a crash."""
    root = make_workspace(tmp_path / "project")
    shut = tmp_path / "shut"
    shut.mkdir()
    shut.chmod(0)

    try:
        with pytest.raises(FlowNotFound) as refused:
            workspace.listing(root, str(shut))
    finally:
        shut.chmod(0o700)

    assert "cannot be read" in str(refused.value)


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


def test_the_record_is_claimed_exclusively(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    first = workspace.new_record(root, port=1234, token="first")

    assert workspace.claim_record(first) is None
    holder = workspace.claim_record(workspace.new_record(root, port=9999, token="two"))

    assert holder is not None
    assert (holder.port, holder.token) == (1234, "first")
    assert workspace.read_record(root) == first


def test_only_the_daemon_that_registered_clears_the_record(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    record = workspace.new_record(root, port=1234, token="t")
    workspace.write_record(record)

    workspace.clear_record(root, pid=record.pid + 1)
    assert workspace.read_record(root) == record

    workspace.clear_record(root, pid=record.pid)
    assert workspace.read_record(root) is None


def test_one_workspace_has_one_record_however_it_is_spelled(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    spelled = root / "churn.flow" / ".."

    assert workspace.record_path(spelled) == workspace.record_path(root)
    assert workspace.registered_roots() == set()
    workspace.write_record(workspace.new_record(spelled, port=1, token="t"))
    assert workspace.registered_roots() == {root}
