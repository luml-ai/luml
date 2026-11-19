import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from lumlflow import __version__
from lumlflow.flow.daemon import workspace
from lumlflow.flow.daemon.workspace import DaemonRecord
from lumlflow.flow.errors import FlowAmbiguous, FlowError, FlowNotFound
from lumlflow.flow.store.flowstore import CELLS_DIRNAME

from tests.helpers.daemon import daemon_api, make_workspace


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
    assert listing.files == [root / "notes.txt"]


async def test_rpc_listing_includes_metadata_and_hidden_is_opt_in(tmp_path: Path):
    root = make_workspace(
        tmp_path / "work",
        flows=("analysis", ".private"),
        files={"report.md": "report", ".env": "env", "build": "excluded"},
    )
    for name in ("Data", ".venv", ".lumlflow"):
        (root / name).mkdir()
    (root / ".gitignore").write_text("report.md\n")
    async with daemon_api(root) as api:
        page = await api.workspace_list({})
        hidden = await api.workspace_list({"show_hidden": True})

    assert page["total"] == 3 and page["next_offset"] is None
    assert [row["name"] for row in page["flows"]] == ["analysis"]
    for group, name in (("folders", "Data"), ("files", "report.md")):
        (row,) = page[group]
        entry = root / name
        assert (row["name"], row["path"], row["is_symlink"]) == (
            name,
            str(entry),
            False,
        )
        modified = datetime.fromisoformat(row["modified_at"])
        assert modified == datetime.fromtimestamp(entry.stat().st_mtime, UTC)
        assert modified.utcoffset() == UTC.utcoffset(None)
    assert page["files"][0]["size"] == len(b"report\n")
    assert [r["name"] for r in hidden["flows"]] == [".private", "analysis"]
    assert [r["name"] for r in hidden["folders"]] == [".venv", "Data"]
    assert [r["name"] for r in hidden["files"]] == [
        ".env",
        ".gitignore",
        "build",
        "report.md",
    ]


async def test_workspace_file_metadata_for_bookmarks(tmp_path: Path):
    root = make_workspace(tmp_path / "work", files={".env": "hidden"})
    hidden = root / ".env"
    async with daemon_api(root) as api:
        lookup = api.methods["workspace.file"]
        row = (await lookup({"path": str(hidden)}))["file"]
        assert row["path"] == str(hidden)
        assert row["size"] == hidden.stat().st_size
        assert row["name"] == ".env"
        for missing in (root / "gone" / "file", root, root / ".lumlflow" / "log"):
            assert (await lookup({"path": str(missing)}))["file"] is None


async def test_rpc_pages_across_groups_in_display_order(tmp_path: Path):
    root = make_workspace(tmp_path / "work", flows=("apple", "Zebra", "apple-2"))
    for name in ("Trees", "birds"):
        (root / name).mkdir()
    for name in ("zoo", "A", "bees"):
        (root / name).touch()
    async with daemon_api(root) as api:
        page = await api.workspace_list({"offset": 1, "limit": 5})
        final = await api.workspace_list({"offset": page["next_offset"]})
        past = await api.workspace_list({"offset": page["total"] + 1})
    assert [r["name"] for r in page["flows"]] == ["apple-2", "Zebra"]
    assert [r["name"] for r in page["folders"]] == ["birds", "Trees"]
    assert [r["name"] for r in page["files"]] == ["A"]
    assert [r["name"] for r in final["files"]] == ["bees", "zoo"]
    assert final["next_offset"] is None
    assert past["total"] == 8 and past["next_offset"] is None
    assert past["files"] == past["flows"] == past["folders"] == []


async def test_default_and_maximum_page_size(tmp_path: Path):
    root = make_workspace(tmp_path / "work", flows=())
    for i in range(4500):
        (root / str(i)).touch()
    async with daemon_api(root) as api:
        pages = [
            await api.workspace_list({}),
            await api.workspace_list({"offset": 2000, "limit": 9999}),
            await api.workspace_list({"offset": 4000}),
        ]
    assert [p["total"] for p in pages] == [4500, 4500, 4500]
    assert [p["next_offset"] for p in pages] == [2000, 4000, None]
    assert [len(p["files"]) for p in pages] == [2000, 2000, 500]
    assert len({row["name"] for p in pages for row in p["files"]}) == 4500


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": "3"},
        {"offset": 0.5},
        {"limit": True},
        {"show_hidden": "false"},
    ],
)
async def test_rpc_rejects_invalid_listing_parameters(tmp_path: Path, params: dict):
    async with daemon_api(tmp_path) as api:
        with pytest.raises(FlowError):
            await api.workspace_list(params)


@pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
async def test_listed_links_keep_their_paths_and_follow_targets(tmp_path: Path):
    root = make_workspace(tmp_path / "work", flows=())
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "report.md").write_bytes(b"report")
    (root / "data").symlink_to(target, target_is_directory=True)
    (root / "file").symlink_to(target / "report.md")
    broken = root / "latest.csv"
    broken.symlink_to(target / "gone")

    async with daemon_api(root) as api:
        page = await api.workspace_list({})
        linked = await api.workspace_list({"directory": str(root / "data")})
    (folder,) = page["folders"]
    assert folder["is_symlink"] and folder["path"] == str(root / "data")
    assert linked["files"][0]["name"] == "report.md"
    file, missing = page["files"]
    assert (
        file["path"] == str(root / "file") and file["is_symlink"] and file["size"] == 6
    )
    assert missing["path"] == str(broken) and missing["is_symlink"]
    assert missing["size"] is None
    assert datetime.fromisoformat(missing["modified_at"]) == datetime.fromtimestamp(
        broken.lstat().st_mtime, UTC
    )


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
def test_a_linked_flow_is_listed_at_its_own_path(tmp_path: Path):
    target = make_workspace(tmp_path / "elsewhere", flows=("churn",)) / "churn.flow"
    root = make_workspace(tmp_path / "project", flows=())
    (root / "linked.flow").symlink_to(target)

    (flow,) = workspace.list_directory(root).flows

    assert (flow.name, flow.path, flow.relpath) == (
        "linked",
        root / "linked.flow",
        "linked.flow",
    )


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


async def test_implicit_flow_selection_includes_hidden_notebooks(tmp_path: Path):
    root = make_workspace(tmp_path / "work", flows=("visible", ".hidden"))
    with pytest.raises(FlowAmbiguous, match=r"\.hidden"):
        workspace.select_flow(root)
    async with daemon_api(root) as api:
        with pytest.raises(FlowAmbiguous, match=r"\.hidden"):
            await api.run({"target": "score"})


@pytest.mark.skipif(sys.platform == "win32", reason="requires symlinks")
async def test_link_kind_comes_from_its_target(tmp_path: Path):
    root = make_workspace(tmp_path / "work", flows=())
    target = make_workspace(tmp_path / "ordinary")
    folder = root / "alias.flow"
    notebook = root / "experiment"
    folder.symlink_to(target, target_is_directory=True)
    notebook.symlink_to(target / "churn.flow", target_is_directory=True)
    async with daemon_api(root) as api:
        listing = await api.workspace_list({})
        assert [row["path"] for row in listing["folders"]] == [str(folder)]
        assert [row["path"] for row in listing["flows"]] == [str(notebook)]
        with pytest.raises(FlowNotFound):
            await api.flow_open({"flow": str(folder)})
        await api.flow_open({"flow": str(notebook)})
        await api.flow_delete({"flow": str(notebook)})
        await api.file_delete({"path": str(folder)})
    assert not folder.is_symlink() and not notebook.is_symlink()
    assert target.is_dir() and not (target / ".lumlflow").exists()
    assert (target / "churn.flow").is_dir()
