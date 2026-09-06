"""The daemon API over a real workspace: list, init, open, run, delete.

The end-to-end run here is the whole stack — a cell file goes through
acceptance, the scheduler plans it, a kernel process materializes it, and the
store records it — on a workspace holding two flows, because a workspace daemon
that hosts one flow proves nothing about the one that hosts two.
"""

import asyncio
import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from lumlflow.flow.daemon import envs, queries, workspace
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.daemon.hub import FlowSession, Hub
from lumlflow.flow.daemon.stream import Streams
from lumlflow.flow.dsl import portable
from lumlflow.flow.errors import FlowAlreadyExists, FlowError, FlowNotFound
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.flow.store.models import RunRecorded
from lumlflow.tracker import TrackerProvider

from tests.daemon.helpers import (
    BROKEN_CELL,
    FRAME_CELL,
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    fake_venv,
    flow_named,
    make_workspace,
    ops_of,
    slice_of,
    slugs,
    source_of,
    transactions,
    values_in,
    write_cell,
    write_file,
)

MODEL_CELL = """
class Train:
    produces = {"model": "model"}

    def materialize(self, ctx):
        return {"model": "WEIGHTS"}
"""

MODEL_AND_EXPERIMENT_CELL = """
class Train:
    produces = {"model": "model", "run": "experiment"}

    def materialize(self, ctx):
        return {"model": "WEIGHTS", "run": ctx.tracker.record}
"""

EXPERIMENT_ONLY_CELL = """
class Evaluate:
    produces = {"metrics": "experiment"}

    def materialize(self, ctx):
        return {"metrics": ctx.tracker.record}
"""

TRACKER_STORE_CELL = """
class Tracked:
    produces = {"run": "experiment"}

    def materialize(self, ctx):
        return {"run": ctx.tracker.record}
"""

NOTE_CELL = '''
class Note:
    """A note placed among the compute cells."""
'''

TRAIN_MODEL_CELL = """
class TrainModel:
    produces = {"model": "asset"}

    def materialize(self, ctx):
        return {"model": "WEIGHTS"}
"""

EVALUATE_CELL = """
class Evaluate:
    consumes = {"model": "train_model.model"}
    produces = {"score": "asset"}

    def materialize(self, ctx, model):
        return {"score": len(model)}
"""

INDEPENDENT_EVALUATE_CELL = """
class Evaluate:
    produces = {"score": "asset"}

    def materialize(self, ctx):
        return {"score": 1}
"""


async def test_the_landing_page_lists_flows_beneath_the_requested_directory(
    tmp_path: Path,
) -> None:
    launch = make_workspace(tmp_path / "launch", flows=("launch",))
    project = make_workspace(tmp_path / "project", flows=("parent",))
    requested = make_workspace(project / "sub", flows=("sales",))
    make_workspace(requested / "nested", flows=("sweep",))

    async with daemon_api(launch) as api:
        listed = await api.workspace_list({"directory": str(requested)})

        assert api.hub.flows() == []

    assert listed == {
        "directory": str(requested),
        "flows": [
            {
                "name": "sales",
                "path": str(requested / "sales.flow"),
                "relative_path": "sales.flow",
            },
            {
                "name": "sweep",
                "path": str(requested / "nested" / "sweep.flow"),
                "relative_path": "nested/sweep.flow",
            },
        ],
    }


# Whose `helpers.py` a cell imports is the whole question, so the answer comes
# back as the marker each workspace's copy declares.
WHERE_CELL = """
class Where:
    \"\"\"Reports the workspace whose code it can import.\"\"\"
    produces = {"where": "asset"}

    def materialize(self, ctx):
        import helpers

        return {"where": {"marker": helpers.MARKER}}
"""


WORKSPACE_CELL = """
class Workspace:
    produces = {"facts": "asset"}

    def materialize(self, ctx):
        import json
        from pathlib import Path

        temporary = ctx.tempdir()
        (temporary / "marker.txt").write_text("temporary")
        return {
            "facts": json.dumps(
                {
                    "cwd": str(Path.cwd()),
                    "workspace": str(ctx.workspace_dir),
                    "data": Path("data.csv").read_text(),
                    "temporary": str(temporary),
                }
            )
        }
"""


async def test_a_flow_outside_the_listing_opens_in_the_same_daemon(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    other = make_workspace(tmp_path / "other", flows=("sales",))
    sales = other / "sales.flow"
    write_cell(sales, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        listed = await api.workspace_list({"directory": str(other)})
        found = listed["flows"][0]
        opened = await api.flow_open({"flow": found["path"]})
        ran = await api.run({"flow": found["path"], "target": "score"})

    assert found["path"] == str(sales)
    assert (opened["flow"], opened["path"]) == ("sales", sales.as_posix())
    assert opened["checked_out"] and ran["executed"] == ["score"]


async def test_a_flow_opened_from_outside_runs_under_its_own_workspace(
    tmp_path: Path,
):
    """One venv and one set of helpers per workspace, whoever hosts the flow.

    A flow this daemon opened from above the launch directory imports the code
    sitting beside *it*: handing it the launch workspace's environment would be
    an environment nobody installed for it.
    """
    root = make_workspace(tmp_path / "project", files={"helpers.py": "MARKER = 1"})
    other = make_workspace(
        tmp_path / "other", flows=("sales",), files={"helpers.py": "MARKER = 2"}
    )
    write_cell(other / "sales.flow", "where", WHERE_CELL)

    async with daemon_api(root) as api:
        ran = await api.run({"flow": str(other / "sales.flow"), "target": "where"})
        session = api.hub.session(str(other / "sales.flow"))
        hosted = {
            ref.name: api.hub.open(ref).workspace_dir
            for ref in workspace.find_flows(root)
        }

    assert ran["executed"] == ["where"]
    assert session.workspace_dir == other
    assert values_in(other / "sales.flow") == [{"marker": 2}]
    # And nothing moved under the flows the launch directory does contain.
    assert hosted == {"churn": root}


async def test_a_nested_flow_runs_from_its_containing_directory(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project", flows=())
    containing = make_workspace(
        root / "experiments" / "q3",
        flows=("churn",),
        files={"data.csv": "payload"},
    )
    flow = containing / "churn.flow"
    write_cell(flow, "workspace", WORKSPACE_CELL)

    async with daemon_api(root) as api:
        outcome = await api.run({"flow": "churn", "target": "workspace"})
        session = api.hub.session("churn")

    assert outcome["executed"] == ["workspace"]
    assert session.workspace_dir == containing
    (facts,) = values_in(flow)
    temporary = Path(facts.pop("temporary"))
    assert facts == {
        "cwd": str(containing),
        "workspace": str(containing),
        "data": "payload\n",
    }
    assert not temporary.exists()


async def test_flow_init_scaffolds_a_store_and_leaves_the_flow_unbound(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        created = await api.flow_init({"name": "churn"})
        listed = await api.workspace_list({"directory": str(root)})
        # The API path creates a flow, never a checkout: binding the worktree
        # and projecting `main` into `cells/` is what `lumlflow init` adds.
        bound = api.hub.session("churn").store.branches.bound_branch()

    assert created["flow"] == "churn"
    assert created["path"] == str(root / "churn.flow")
    assert created["branch"] == "main"
    assert _kernel_state(created) == ("stopped", False, [])
    assert store_dir(root / "churn.flow").is_dir()
    assert [flow["relative_path"] for flow in listed["flows"]] == ["churn.flow"]
    assert bound is None


async def test_flow_init_creates_in_the_directory_the_caller_names(tmp_path: Path):
    launch = make_workspace(tmp_path / "launch", flows=())
    destination = make_workspace(tmp_path / "destination", flows=())

    async with daemon_api(launch) as api:
        created = await api.flow_init({"name": "sales", "directory": str(destination)})

    assert created["path"] == str(destination / "sales.flow")
    assert store_dir(destination / "sales.flow").is_dir()
    assert not (launch / "sales.flow").exists()


async def test_a_flow_with_cells_opens_on_them_unmaterialized(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})

    assert slugs(opened) == ["report", "score"]
    assert slugs(opened, "unmaterialized") == ["report", "score"]
    report = next(cell for cell in opened["cells"] if cell["slug"] == "report")
    assert report["outputs"] == ["report"]
    assert report["consumes"] == {"summary": "score.summary"}
    # `report` was read before `score` existed in the namespace; the rescan
    # binds it anyway rather than leaving a dangling reference behind.
    assert report["flags"] == []


async def test_downstream_scaffolds_one_non_experiment_output_unless_all_requested(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new(
            {"flow": "churn", "slug": "train", "source": MODEL_AND_EXPERIMENT_CELL}
        )
        await api.cells_new({"flow": "churn", "slug": "report", "after": "train"})
        await api.cells_new(
            {
                "flow": "churn",
                "slug": "audit",
                "after": "train",
                "outputs": "all",
            }
        )
        listed = await api.cells_list({"flow": "churn"})
        report = await api.cells_show({"flow": "churn", "slug": "report"})
        audit = await api.cells_show({"flow": "churn", "slug": "audit"})

    train = next(cell for cell in listed["cells"] if cell["slug"] == "train")
    assert train["primary"] == "run"
    assert report["consumes"] == {"model": "train.model"}
    assert "def materialize(self, ctx, model):" in report["source"]
    assert audit["consumes"] == {
        "model": "train.model",
        "run": "train.run",
    }
    assert "def materialize(self, ctx, model, run):" in audit["source"]


async def test_downstream_scaffolds_an_experiment_when_it_is_the_only_output(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new(
            {
                "flow": "churn",
                "slug": "evaluate",
                "source": EXPERIMENT_ONLY_CELL,
            }
        )
        await api.cells_new({"flow": "churn", "slug": "report", "after": "evaluate"})
        report = await api.cells_show({"flow": "churn", "slug": "report"})

    assert report["consumes"] == {"metrics": "evaluate.metrics"}
    assert "def materialize(self, ctx, metrics):" in report["source"]


async def test_an_experiment_cell_uses_the_daemons_tracker_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tracker: TrackerProvider,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "tracked", TRACKER_STORE_CELL)
    unrelated = tmp_path / "unrelated"
    monkeypatch.setenv("BACKEND_STORE_URI", str(unrelated))
    monkeypatch.setenv("LUML_BACKEND_STORE_URI", str(unrelated))

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        result = await api.run({"flow": "churn", "target": "tracked"})

    assert result["executed"] == ["tracked"]
    assert [record.name for record in tracker.list_experiments()] == ["tracked"]
    assert not unrelated.exists()


async def test_opening_a_flow_reports_the_settings_a_panel_renders(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        session.store.manifest.settings.reactivity = "lazy"
        session.store.save_manifest()
        relaxed = await api.flow_open({"flow": "churn"})

    assert opened["settings"] == {
        "reactivity": "auto",
        "eager_cost_threshold_s": 5.0,
    }
    assert relaxed["settings"]["reactivity"] == "lazy"


async def test_anchored_adds_persist_exact_keys_across_rename_and_reload(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new({"flow": "churn", "slug": "first", "source": NOTE_CELL})
        await api.cells_new({"flow": "churn", "slug": "last", "source": NOTE_CELL})
        assert "order" not in yaml.safe_load((flow / "flow.yaml").read_text())
        unmapped = await api.cells_list({"flow": "churn"})
        assert all(
            cell["order"] == str(cell["created_step"]) for cell in unmapped["cells"]
        )

        await api.cells_new(
            {
                "flow": "churn",
                "slug": "placed",
                "source": NOTE_CELL,
                "anchor": "first",
            }
        )
        once = await api.cells_list({"flow": "churn"})
        by_slug = {cell["slug"]: cell for cell in once["cells"]}
        placed_uid = slice_of(api.hub.session("churn"), "main")["placed"].uid
        placed_key = yaml.safe_load((flow / "flow.yaml").read_text())["order"][
            placed_uid
        ]

        await api.cells_new(
            {
                "flow": "churn",
                "slug": "closer",
                "source": NOTE_CELL,
                "anchor": "first",
            }
        )
        await api.rename({"flow": "churn", "slug": "placed", "to": "renamed_placed"})
        renamed = await api.cells_show({"flow": "churn", "slug": "renamed_placed"})
        after = await api.cells_list({"flow": "churn"})
        after_by_slug = {cell["slug"]: cell for cell in after["cells"]}

    async with daemon_api(root) as api:
        reloaded = await api.cells_show({"flow": "churn", "slug": "renamed_placed"})

    assert (
        Decimal(str(by_slug["first"]["order"]))
        < Decimal(placed_key)
        < Decimal(str(by_slug["last"]["order"]))
    )
    assert (
        Decimal(str(after_by_slug["first"]["order"]))
        < Decimal(str(after_by_slug["closer"]["order"]))
        < Decimal(str(after_by_slug["renamed_placed"]["order"]))
    )
    assert (
        yaml.safe_load((flow / "flow.yaml").read_text())["order"][placed_uid]
        == placed_key
    )
    assert renamed["order"] == reloaded["order"] == placed_key


async def test_an_unknown_or_other_lane_anchor_changes_nothing(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new({"flow": "churn", "slug": "shared", "source": NOTE_CELL})
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_new(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "exp_only",
                "source": NOTE_CELL,
            }
        )
        session = api.hub.session("churn")
        manifest_before = (flow / "flow.yaml").read_bytes()
        journal_before = transactions(session)

        with pytest.raises(FlowError, match="nowhere"):
            await api.cells_new(
                {
                    "flow": "churn",
                    "slug": "refused_unknown",
                    "source": NOTE_CELL,
                    "anchor": "nowhere",
                }
            )
        with pytest.raises(FlowError, match="exp_only"):
            await api.cells_new(
                {
                    "flow": "churn",
                    "branch": "main",
                    "slug": "refused_lane",
                    "source": NOTE_CELL,
                    "anchor": "exp_only",
                }
            )

        assert (flow / "flow.yaml").read_bytes() == manifest_before
        assert transactions(session) == journal_before
        assert set(slice_of(session, "main")) == {"shared"}


async def test_a_duplicate_is_anchored_on_its_original(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new({"flow": "churn", "slug": "original", "source": NOTE_CELL})
        await api.cells_new({"flow": "churn", "slug": "last", "source": NOTE_CELL})
        original = await api.cells_show({"flow": "churn", "slug": "original"})

        await api.cells_new(
            {
                "flow": "churn",
                "slug": "original_copy",
                "source": original["source"],
            }
        )
        listed = await api.cells_list({"flow": "churn"})

    by_slug = {cell["slug"]: Decimal(str(cell["order"])) for cell in listed["cells"]}
    assert by_slug["original"] < by_slug["original_copy"] < by_slug["last"]


async def test_delete_drops_the_key_and_rewind_uses_the_creation_step(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new({"flow": "churn", "slug": "first", "source": NOTE_CELL})
        await api.cells_new(
            {
                "flow": "churn",
                "slug": "placed",
                "source": NOTE_CELL,
                "anchor": "first",
            }
        )
        placed = await api.cells_show({"flow": "churn", "slug": "placed"})
        assert placed["order"] != str(placed["created_step"])

        await api.cells_delete({"flow": "churn", "slug": "placed"})
        assert "order" not in yaml.safe_load((flow / "flow.yaml").read_text())

        await api.rewind({"flow": "churn", "to_step": placed["created_step"]})
        restored = await api.cells_show({"flow": "churn", "slug": "placed"})

    assert restored["order"] == str(restored["created_step"])
    assert "order" not in yaml.safe_load((flow / "flow.yaml").read_text())


async def test_slug_index_tracks_all_lanes_and_rewind_restores_a_deleted_slug(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    manifest_path = root / "churn.flow" / "flow.yaml"

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        first = await api.cells_new({"flow": "churn"})
        await api.cells_new({"flow": "churn"})
        await api.cells_new({"flow": "churn"})
        first_detail = await api.cells_show({"flow": "churn", "slug": first["slug"]})
        await api.fork({"flow": "churn", "name": "exp"})

        await api.cells_delete({"flow": "churn", "slug": first["slug"]})
        still_selected = yaml.safe_load(manifest_path.read_text())["cells"]
        await api.cells_delete(
            {"flow": "churn", "branch": "exp", "slug": first["slug"]}
        )
        fully_deleted = yaml.safe_load(manifest_path.read_text())["cells"]

        added = await api.cells_new({"flow": "churn"})
        await api.rewind(
            {
                "flow": "churn",
                "branch": "main",
                "to_step": first_detail["created_step"],
            }
        )
        restored = yaml.safe_load(manifest_path.read_text())["cells"]

    assert first["slug"] == "untitled_1"
    assert still_selected[first["slug"]] == first_detail["uid"]
    assert first["slug"] not in fully_deleted
    assert added["slug"] == "untitled_4"
    assert restored[first["slug"]] == first_detail["uid"]
    assert set(restored) == {"untitled_1", "untitled_2", "untitled_3"}


async def test_reorder_checks_the_called_lanes_topology_and_allows_archived_lanes(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new(
            {"flow": "churn", "slug": "train_model", "source": TRAIN_MODEL_CELL}
        )
        await api.cells_new(
            {"flow": "churn", "slug": "evaluate", "source": EVALUATE_CELL}
        )
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_edit(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "evaluate",
                "source": INDEPENDENT_EVALUATE_CELL,
            }
        )
        session = api.hub.session("churn")
        manifest_before = (flow / "flow.yaml").read_bytes()
        journal_before = transactions(session)

        with pytest.raises(FlowError, match="train_model"):
            await api.cells_reorder(
                {
                    "flow": "churn",
                    "branch": "main",
                    "slug": "evaluate",
                    "before": "train_model",
                }
            )
        with pytest.raises(FlowError, match="evaluate"):
            await api.cells_reorder(
                {
                    "flow": "churn",
                    "branch": "main",
                    "slug": "train_model",
                    "after": "evaluate",
                }
            )

        assert (flow / "flow.yaml").read_bytes() == manifest_before
        assert transactions(session) == journal_before

        moved = await api.cells_reorder(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "evaluate",
                "before": "train_model",
            }
        )
        train_uid = slice_of(session, "exp")["train_model"].uid
        assert Decimal(moved["order"]) < session.store.effective_order()[train_uid]

        archived = await api.archive(
            {"flow": "churn", "branch": "exp", "intent": "retired experiment"}
        )
        moved_back = await api.cells_reorder(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "evaluate",
                "after": "train_model",
            }
        )
        train_order_after = session.store.effective_order()[train_uid]

    assert archived == {"branch": "exp", "archived": True}
    assert moved_back["branch"] == "exp"
    assert Decimal(moved_back["order"]) > train_order_after


async def test_reorder_refuses_missing_lane_cells_and_an_invalid_position(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.cells_new({"flow": "churn", "slug": "shared", "source": NOTE_CELL})
        await api.fork({"flow": "churn", "name": "exp"})
        await api.cells_new(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "exp_only",
                "source": NOTE_CELL,
            }
        )

        with pytest.raises(FlowError, match="exp_only"):
            await api.cells_reorder(
                {
                    "flow": "churn",
                    "branch": "main",
                    "slug": "exp_only",
                    "before": "shared",
                }
            )
        with pytest.raises(FlowError, match="exp_only"):
            await api.cells_reorder(
                {
                    "flow": "churn",
                    "branch": "main",
                    "slug": "shared",
                    "before": "exp_only",
                }
            )
        with pytest.raises(FlowError, match="exactly one"):
            await api.cells_reorder({"flow": "churn", "slug": "shared"})
        with pytest.raises(FlowError, match="exactly one"):
            await api.cells_reorder(
                {
                    "flow": "churn",
                    "slug": "shared",
                    "before": "shared",
                    "after": "shared",
                }
            )
        with pytest.raises(FlowError, match="itself"):
            await api.cells_reorder(
                {"flow": "churn", "slug": "shared", "before": "shared"}
            )


async def test_reorder_pushes_state_without_moving_the_journal_cursor(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    streams = Streams()
    hub = Hub(streams=streams)
    try:
        api = Api(hub, directory=root)
        await api.flow_open({"flow": "churn"})
        await api.cells_new({"flow": "churn", "slug": "first", "source": NOTE_CELL})
        await api.cells_new({"flow": "churn", "slug": "last", "source": NOTE_CELL})
        await api.cells_new({"flow": "churn", "slug": "moved", "source": NOTE_CELL})
        session = hub.session("churn")
        before = await api.cells_list({"flow": "churn"})
        before_by_slug = {cell["slug"]: cell for cell in before["cells"]}
        cursor = session.store.next_step - 1
        journal_before = transactions(session)
        watching = streams.subscribe()
        watching.journals.add(session.ref.address)

        result = await api.cells_reorder(
            {
                "flow": "churn",
                "slug": "moved",
                "before": "last",
            }
        )
        frame = await asyncio.wait_for(watching.next(), timeout=1)

        assert result["slug"] == "moved"
        assert result["uid"] == slice_of(session, "main")["moved"].uid
        assert (
            Decimal(str(before_by_slug["first"]["order"]))
            < Decimal(result["order"])
            < Decimal(str(before_by_slug["last"]["order"]))
        )
        assert frame == {
            "channel": "journal",
            "type": "state",
            "state": "order_changed",
            "flow": session.ref.address,
            "step": cursor,
        }
        assert session.store.next_step - 1 == cursor
        assert transactions(session) == journal_before
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(watching.next(), timeout=0.05)
    finally:
        await hub.close()


async def test_removed_surfaces_are_not_api_methods(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        removed = {
            "secrets.set",
            "secrets.list",
            "env.add",
            "env.remove",
            "set_focus",
            "asset.diff",
        }

        assert removed.isdisjoint(api.methods)
        assert "env.status" in api.methods


async def test_status_covers_every_flow_and_names_the_interpreter(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        status = await api.status({})

    assert [flow["flow"] for flow in status["flows"]] == ["churn", "sales"]
    assert status["workspace"] == str(root)
    assert status["python"]["source"] == "lumlflow"
    assert slugs(flow_named(status, "churn")) == ["score"]
    assert slugs(flow_named(status, "sales")) == []


async def test_open_and_status_carry_the_store_flow_id(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})
        status = await api.status({"flow": "churn"})
        flow_id = api.hub.session("churn").store.manifest.flow_id

    assert opened["flow_id"] == flow_id
    assert flow_named(status, "churn")["flow_id"] == flow_id


async def test_status_lists_only_flows_beneath_the_requested_directory(
    tmp_path: Path,
):
    launch = make_workspace(tmp_path / "launch", flows=("launch",))
    requested = make_workspace(tmp_path / "requested", flows=("sales",))

    async with daemon_api(launch) as api:
        status = await api.status({"directory": str(requested)})

    assert status["workspace"] == str(requested)
    assert [flow["path"] for flow in status["flows"]] == [str(requested / "sales.flow")]


async def test_a_run_crosses_daemon_kernel_and_store_in_two_flows(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)
    write_cell(root / "sales.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        churn = await api.run({"flow": "churn", "target": "report"})
        sales = await api.run({"flow": "sales", "target": "score"})
        status = await api.status({})
        kernels = {
            name: (api.hub.session(name).kernel.handshake or {}).get("pid")
            for name in ("churn", "sales")
        }

    assert churn["executed"] == ["score", "report"]
    assert (churn["failed"], churn["branch"]) == (None, "main")
    assert sales["executed"] == ["score"]
    assert slugs(flow_named(status, "churn"), "synced") == ["report", "score"]
    assert slugs(flow_named(status, "sales"), "synced") == ["score"]
    # One kernel per flow, and each flow's bytes land in its own store.
    assert kernels["churn"] not in (None, kernels["sales"])
    assert values_in(root / "sales.flow") == [{"auc": 0.91}]
    assert values_in(root / "churn.flow") == [{"auc": 0.91}, {"auc_pct": 91.0}]


async def test_a_model_run_never_uploads_or_writes_project_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(
        tmp_path / "project",
        files={
            "pyproject.toml": "[project]\nname = 'project'\nversion = '0.1.0'",
            "uv.lock": "version = 1",
        },
    )
    fake_venv(root)
    write_cell(root / "churn.flow", "train", MODEL_CELL)
    project_before = (root / "pyproject.toml").read_bytes()
    lock_before = (root / "uv.lock").read_bytes()
    uv_calls: list[tuple[str, ...]] = []

    async def record_uv(_workspace_dir: Path, *args: str) -> str:
        uv_calls.append(args)
        return ""

    monkeypatch.setattr(envs.shutil, "which", lambda _name: "uv")
    monkeypatch.setattr(envs, "uv", record_uv)

    async with daemon_api(root) as api:
        outcome = await api.run({"target": "train"})
        session = api.hub.session("churn")
        op_names = [op.op for entry in transactions(session) for op in entry.ops]

    assert outcome["executed"] == ["train"]
    assert all(not name.startswith("upload_") for name in op_names)
    assert uv_calls == []
    assert (root / "pyproject.toml").read_bytes() == project_before
    assert (root / "uv.lock").read_bytes() == lock_before


async def test_preflight_names_the_closure_the_run_then_executes(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        before = await api.preflight({"flow": "churn", "target": "report"})
        outcome = await api.run({"flow": "churn", "target": "report"})
        again = await api.run({"flow": "churn", "target": "report"})
        after = await api.preflight({"flow": "churn", "target": "report"})

    assert before["recompute"] == ["score", "report"]
    assert before["unknown"] == ["score", "report"]
    assert outcome["executed"] == list(before["recompute"])
    # Nothing changed in between: the synced parent is not even a candidate,
    # and the target itself is pruned on the key it already ran under.
    assert (again["executed"], again["pruned"]) == ([], ["report"])
    assert after["recompute"] == []


async def test_run_without_a_target_runs_lane_leaves_and_prunes_current_ones(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)
    write_cell(flow, "independent", INDEPENDENT_EVALUATE_CELL)

    async with daemon_api(root) as api:
        first = await api.run({"flow": "churn"})
        write_cell(flow, "score", SCORE_CELL.replace("0.91", "0.95"))
        changed = await api.run({"flow": "churn"})
        current = await api.run({"flow": "churn"})

    assert first["targets"] == ["independent", "report"]
    assert set(first["executed"]) == {"independent", "score", "report"}
    assert changed["executed"] == ["score", "report"]
    assert changed["pruned"] == ["independent"]
    assert current["executed"] == []
    assert current["pruned"] == ["independent", "report"]


async def test_run_without_a_target_continues_after_an_independent_failure(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "broken", BROKEN_CELL)
    write_cell(flow, "independent", INDEPENDENT_EVALUATE_CELL)

    async with daemon_api(root) as api:
        outcome = await api.run({"flow": "churn"})

    assert outcome["failures"] == ["broken"]
    assert outcome["failed"] == "broken"
    assert outcome["executed"] == ["independent"]


async def test_run_without_a_target_reports_one_unplannable_leaf_and_runs_the_rest(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(
        flow,
        "dangling",
        """
        class Dangling:
            consumes = {"value": "missing.value"}
            produces = {"result": "asset"}

            def materialize(self, ctx, value):
                return {"result": value}
        """,
    )
    write_cell(flow, "independent", INDEPENDENT_EVALUATE_CELL)

    async with daemon_api(root) as api:
        outcome = await api.run({"flow": "churn"})

    assert outcome["executed"] == ["independent"]
    assert [failure["target"] for failure in outcome["unplanned"]] == ["dangling"]
    assert "missing.value" in outcome["unplanned"][0]["error"]


async def test_cancelling_a_lane_run_does_not_start_its_next_leaf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    first_marker = tmp_path / "first"
    later_marker = tmp_path / "later"
    for slug, marker in (("a_first", first_marker), ("z_later", later_marker)):
        write_cell(
            flow,
            slug,
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
        session = api.hub.open(workspace.select_flow(root, name="churn"))
        ensure_started = session.kernel.ensure_started
        starting = asyncio.Event()
        resume = asyncio.Event()

        async def delayed_start() -> dict[str, Any]:
            starting.set()
            await resume.wait()
            return await ensure_started()

        monkeypatch.setattr(session.kernel, "ensure_started", delayed_start)
        running = asyncio.create_task(api.run({"flow": "churn"}))
        await asyncio.wait_for(starting.wait(), timeout=5)
        left = await api.cancel({"flow": "churn"})
        resume.set()
        outcome = await running

    assert (left["left"], left["stopped"]) == (1, True)
    assert outcome["targets"] == ["a_first", "z_later"]
    assert outcome["abandoned"] is True
    assert not first_marker.exists()
    assert not later_marker.exists()


async def test_forcing_a_run_spends_the_cost_the_store_would_have_saved(
    tmp_path: Path,
):
    """The card's force modifier has to mean something at the far end: without
    this it would read as a rerun and quietly be answered from the memo."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        ordinary = await api.run({"flow": "churn", "target": "score"})
        forced = await api.run({"flow": "churn", "target": "score", "force": True})
        runs = ops_of(api.hub.session("churn"), RunRecorded)

    assert (ordinary["executed"], ordinary["pruned"]) == ([], ["score"])
    assert forced["executed"] == ["score"]
    assert len(runs) == 2


async def test_preflighting_several_targets_counts_a_shared_parent_once(
    tmp_path: Path,
):
    """Rerunning a branch preflights its leaves together — one closure, so the
    parent both of them need is billed the once it will run."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)

    async with daemon_api(root) as api:
        batch = await api.preflight({"flow": "churn", "targets": ["score", "report"]})

    assert batch["recompute"] == ["score", "report"]
    assert batch["target"] == "score, report"


async def test_the_eager_opt_in_survives_the_daemon_that_took_it(tmp_path: Path):
    """A per-asset toggle that lived in one process would be a setting the next
    session silently dropped. It belongs in `flow.yaml`, beside the cost
    threshold it overrides."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.cells_eager({"flow": "churn", "slug": "score", "eager": True})
    async with daemon_api(root) as api:
        after = await api.flow_open({"flow": "churn"})
        off = await api.cells_eager({"flow": "churn", "slug": "score", "eager": False})
        again = await api.cells_list({"flow": "churn"})

    assert [cell["eager"] for cell in after["cells"]] == [True]
    assert off["eager"] is False
    assert [cell["eager"] for cell in again["cells"]] == [False]


async def test_leaving_a_run_nobody_is_waiting_on_says_so(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        left = await api.cancel({"flow": "churn"})

    assert (left["left"], left["stopped"], left["awaiting"]) == (0, False, 0)


async def test_cancelling_during_kernel_start_never_runs_the_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    marker = tmp_path / "executed"
    write_cell(
        root / "churn.flow",
        "slow_start",
        f"""
        class SlowStart:
            produces = {{"value": "asset"}}

            def materialize(self, ctx):
                from pathlib import Path

                Path({str(marker)!r}).touch()
                return {{"value": 1}}
        """,
    )

    async with daemon_api(root) as api:
        session = api.hub.open(workspace.select_flow(root, name="churn"))
        ensure_started = session.kernel.ensure_started
        starting = asyncio.Event()
        resume = asyncio.Event()

        async def delayed_start() -> dict[str, Any]:
            starting.set()
            await resume.wait()
            return await ensure_started()

        monkeypatch.setattr(session.kernel, "ensure_started", delayed_start)
        running = asyncio.create_task(
            api.run({"flow": "churn", "target": "slow_start"})
        )
        await asyncio.wait_for(starting.wait(), timeout=5)
        left = await api.cancel({"flow": "churn"})
        resume.set()
        outcome = await running
        async with asyncio.timeout(30):
            while session.queue.busy:
                await asyncio.sleep(0.01)
        runs = ops_of(session, RunRecorded)

    assert (left["left"], left["stopped"]) == (1, True)
    assert outcome["abandoned"] is True
    assert [run.state for run in runs] == ["cancelled"]
    assert not marker.exists()


async def test_a_failing_cell_is_recorded_not_raised(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        outcome = await api.run({"flow": "churn", "target": "score"})
        opened = await api.flow_open({"flow": "churn"})

    assert outcome["failed"] == "score"
    assert outcome["executed"] == []
    assert slugs(opened, "failed") == ["score"]


@pytest.mark.parametrize("source", ["", "   \n"])
async def test_an_empty_edit_changes_neither_file_nor_journal(
    tmp_path: Path, source: str
) -> None:
    root = make_workspace(tmp_path / "project")
    cell_path = write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        file_before = cell_path.read_bytes()
        head_before = slice_of(session, "main")["score"].version_id
        journal_before = transactions(session)

        with pytest.raises(FlowError, match=r"`score`.*empty"):
            await api.cells_edit({"flow": "churn", "slug": "score", "source": source})

        assert cell_path.read_bytes() == file_before
        assert slice_of(session, "main")["score"].version_id == head_before
        assert transactions(session) == journal_before


async def test_an_edit_between_runs_is_picked_up_without_a_watcher(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        write_cell(
            root / "churn.flow",
            "score",
            SCORE_CELL.replace("0.91", "0.93"),
        )
        outcome = await api.run({"flow": "churn", "target": "score"})

    assert outcome["executed"] == ["score"]
    # Both runs' bytes are in the store; the edit's is what the second produced.
    assert values_in(root / "churn.flow") == [{"auc": 0.91}, {"auc": 0.93}]


async def test_running_a_fork_never_hands_it_the_worktrees_edit(tmp_path: Path):
    """The files are one branch's slice. Rescanning them onto the branch a run
    happens to name would make every fork adopt the worktree by standing still,
    and pin-at-fork says a fork takes an update by adopt or not at all."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        session = api.hub.session("churn")
        session.store.branches.fork("sweep", from_branch="main")
        pinned = slice_of(session, "sweep")["score"].version_id

        write_cell(root / "churn.flow", "score", SCORE_CELL.replace("0.91", "0.93"))
        await api.run({"flow": "churn", "branch": "sweep", "target": "score"})
        on_sweep = slice_of(session, "sweep")["score"].version_id
        on_main = slice_of(session, "main")["score"].version_id

    assert on_sweep == pinned
    assert on_main != pinned
    # The fork ran what it pinned, not what the worktree now holds.
    assert values_in(root / "churn.flow") == [{"auc": 0.91}]


async def test_adopting_a_renamed_cell_rewires_consumers_by_uid(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})
        session = api.hub.session("churn")
        score_uid = slice_of(session, "main")["score"].uid
        await api.fork({"flow": "churn", "name": "exp"})
        await api.rename(
            {
                "flow": "churn",
                "branch": "exp",
                "slug": "score",
                "to": "points",
            }
        )

        adopted = await api.adopt(
            {
                "flow": "churn",
                "slug": "points",
                "from_branch": "exp",
            }
        )
        listed = await api.cells_list({"flow": "churn", "branch": "main"})
        outcome = await api.run({"flow": "churn", "target": "report", "force": True})
        here = slice_of(session, "main")

    report = next(cell for cell in listed["cells"] if cell["slug"] == "report")
    assert adopted["slug"] == "points"
    assert here["points"].uid == score_uid
    assert here["report"].manifest.consumes["summary"].uid == score_uid
    assert (report["state"], report["flags"]) == ("synced", [])
    assert "points.summary" in source_of(flow, "report")
    assert (outcome["failed"], outcome["executed"]) == (None, ["report"])


async def test_deleting_on_an_off_disk_lane_flags_its_consumers(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})
        await api.fork({"flow": "churn", "name": "exp"})

        deleted = await api.cells_delete(
            {"flow": "churn", "branch": "exp", "slug": "score"}
        )
        listed = await api.cells_list({"flow": "churn", "branch": "exp"})

    report = next(cell for cell in listed["cells"] if cell["slug"] == "report")
    assert deleted["dangling"] == ["report"]
    assert report["state"] == "unsynced"
    assert [flag["code"] for flag in report["flags"]] == ["dangling_ref"]
    assert "score" in str(report["flags"][0]["detail"])
    assert any("score" in cause for cause in report["causes"])
    assert (flow / "cells" / "score.py").exists()


async def test_importing_a_renamed_cell_rewires_existing_consumers(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path / "project")
    flow = root / "churn.flow"
    write_cell(flow, "score", SCORE_CELL)
    write_cell(flow, "report", REPORT_CELL)

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})
        session = api.hub.session("churn")
        score_uid = slice_of(session, "main")["score"].uid
        carried = portable.render(
            [portable.PortableCell(slug="points", source=source_of(flow, "score"))],
            flow="churn",
            branch="exp",
        )

        imported = await api.import_cells({"flow": "churn", "source": carried})
        listed = await api.cells_list({"flow": "churn"})
        outcome = await api.run({"flow": "churn", "target": "report", "force": True})
        here = slice_of(session, "main")

    report = next(cell for cell in listed["cells"] if cell["slug"] == "report")
    assert [cell["slug"] for cell in imported["cells"]] == ["points"]
    assert here["points"].uid == score_uid
    assert here["report"].manifest.consumes["summary"].uid == score_uid
    assert (report["state"], report["flags"]) == ("synced", [])
    assert "points.summary" in source_of(flow, "report")
    assert outcome["failed"] is None


@pytest.mark.parametrize("adopted_first", [False, True])
async def test_a_forced_adopt_name_clash_keeps_the_preexisting_cell(
    tmp_path: Path, adopted_first: bool
) -> None:
    root = make_workspace(tmp_path / "project")

    async with daemon_api(root) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "exp"})
        first_branch = "exp" if adopted_first else "main"
        second_branch = "main" if adopted_first else "exp"
        await api.cells_new(
            {
                "flow": "churn",
                "branch": first_branch,
                "slug": "score",
                "source": SCORE_CELL,
            }
        )
        await api.cells_new(
            {
                "flow": "churn",
                "branch": second_branch,
                "slug": "score",
                "source": SCORE_CELL,
            }
        )
        await api.cells_new(
            {
                "flow": "churn",
                "branch": "main",
                "slug": "report",
                "source": REPORT_CELL,
            }
        )
        session = api.hub.session("churn")
        existing = slice_of(session, "main")["score"]
        incoming = slice_of(session, "exp")["score"]

        adopted = await api.adopt(
            {
                "flow": "churn",
                "slug": "score",
                "from_branch": "exp",
                "force": True,
            }
        )
        here = slice_of(session, "main")

    assert adopted["slug"] == "score_2"
    assert here["score"].uid == existing.uid
    assert here["score_2"].uid == incoming.uid
    assert here["score_2"].version_id != incoming.version_id
    assert here["report"].manifest.consumes["summary"].uid == existing.uid


async def test_a_clone_without_a_store_rebuilds_the_identity_git_carried(
    tmp_path: Path,
):
    """`.lumlflow/` is gitignored, so a second machine gets the cells and
    `flow.yaml` and nothing else. The time plane does not travel through git;
    identity does, and the caches are merely cold."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        first = await api.run({"flow": "churn", "target": "score"})
        committed = api.hub.session("churn")
        flow_id = committed.store.manifest.flow_id
        indexed = dict(committed.store.manifest.cells)
        hashes = _definition_hashes(committed)
        keys = _memo_keys(committed)
        (ran_before,) = ops_of(committed, RunRecorded)
    shutil.rmtree(store_dir(root / "churn.flow"))

    async with daemon_api(root) as fresh:
        opened = await fresh.flow_open({"flow": "churn"})
        session = fresh.hub.session("churn")
        again = await fresh.run({"flow": "churn", "target": "score"})
        rebuilt = _definition_hashes(session)
        relaid = _memo_keys(session)

    assert (session.store.manifest.flow_id, session.store.manifest.cells) == (
        flow_id,
        indexed,
    )
    assert rebuilt == hashes
    assert slugs(opened) == ["score"]
    # The keys line up, so the clone recomputed for want of a materialization
    # carrying one — a cold cache, not a permanently unreachable one.
    assert relaid == keys
    # Nothing was memoized across the clone, and the run produced the same bytes.
    assert (first["executed"], again["executed"]) == (["score"], ["score"])
    assert values_in(root / "churn.flow") == [{"auc": 0.91}]
    # History roots fresh: the rebuilt journal begins at the first step and
    # carries none of the run git never shipped.
    assert [entry.step for entry in transactions(session)][0] == 1
    assert ran_before.mat_id not in {op.mat_id for op in ops_of(session, RunRecorded)}


async def test_listing_a_materialized_flow_starts_no_kernel(tmp_path: Path):
    """Everything a session renders is stored, so a listing that never runs a
    cell never spawns a process — the expand gesture is what starts one."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        await api.hub.session("churn").kernel.stop()

        listed = await api.workspace_list({"directory": str(root)})
        opened = await api.flow_open({"flow": "churn"})
        status = await api.status({})

    assert [flow["relative_path"] for flow in listed["flows"]] == ["churn.flow"]
    assert slugs(opened, "synced") == ["score"]
    assert _kernel_state(opened) == ("stopped", False, [])
    assert _kernel_state(flow_named(status, "churn")) == ("stopped", False, [])


async def test_paging_a_value_starts_the_kernel_the_preview_never_needed(
    tmp_path: Path,
):
    """The other half of the same contract: previews are the kernel-free tier,
    and reading into a value is the gesture that crosses into one — which it
    does by starting a kernel, never by refusing."""
    pytest.importorskip("pandas")
    pytest.importorskip("pyarrow")
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "rows", FRAME_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "rows"})
        await api.hub.session("churn").kernel.stop()
        previewed = await api.asset_preview({"flow": "churn", "target": "rows"})
        stopped = api.hub.session("churn").kernel.state

        paged = await api.asset_page(
            {
                "flow": "churn",
                "target": "rows.rows",
                "query": {"offset": 10, "limit": 3},
            }
        )
        started = api.hub.session("churn").kernel.state

    assert (stopped, started) == ("stopped", "running")
    assert previewed["preview"]["blocks"][0]["block"] == "table"
    assert paged["page"]["rows"] == [[10], [11], [12]]
    assert paged["page"]["total_rows"] == 50


async def test_asset_download_refuses_a_relative_socket_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "train", MODEL_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "train"})
        daemon_cwd = tmp_path / "daemon-cwd"
        daemon_cwd.mkdir()
        monkeypatch.chdir(daemon_cwd)

        with pytest.raises(FlowError, match=r"`to`.*absolute"):
            await api.asset_download(
                {
                    "flow": "churn",
                    "target": "train.model",
                    "to": "relative.model",
                }
            )

    assert list(daemon_cwd.iterdir()) == []


async def test_a_half_written_cell_never_stops_the_flow(tmp_path: Path):
    """Agents iterate through broken states; a rescan that refused one would
    stall the loop it exists to serve."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_cell(root / "churn.flow", "half", "class Half:\n    consumes = {")

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})
        outcome = await api.run({"flow": "churn", "target": "score"})

    half = next(cell for cell in opened["cells"] if cell["slug"] == "half")
    assert [flag["code"] for flag in half["flags"]] == ["invalid"]
    assert outcome["executed"] == ["score"]


async def test_deleting_a_flow_takes_its_store_with_it(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        deleted = await api.flow_delete({"flow": "churn"})
        left = await api.workspace_list({"directory": str(root)})

    assert deleted == {"deleted": "churn", "path": str(root / "churn.flow")}
    assert not (root / "churn.flow").exists()
    assert [flow["relative_path"] for flow in left["flows"]] == ["sales.flow"]


async def test_renaming_a_flow_moves_its_directory_and_keeps_its_store(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        renamed = await api.flow_rename({"flow": "churn", "name": "revenue"})
        left = await api.workspace_list({"directory": str(root)})
        reopened = await api.flow_open({"flow": "revenue"})

    assert renamed == {
        "renamed": "revenue",
        "path": str(root / "revenue.flow"),
        "from": str(root / "churn.flow"),
    }
    assert not (root / "churn.flow").exists()
    assert (root / "revenue.flow").exists()
    assert sorted(flow["relative_path"] for flow in left["flows"]) == [
        "revenue.flow",
        "sales.flow",
    ]
    assert [cell["slug"] for cell in reopened["cells"]] == ["score"]


async def test_renaming_a_flow_onto_an_existing_name_is_refused(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))

    async with daemon_api(root) as api:
        with pytest.raises(FlowAlreadyExists):
            await api.flow_rename({"flow": "churn", "name": "sales"})

    assert (root / "churn.flow").exists()
    assert (root / "sales.flow").exists()


async def test_duplicating_a_flow_copies_its_store_and_leaves_the_source(
    tmp_path: Path,
):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        duplicated = await api.flow_duplicate({"flow": "churn", "name": "churn (copy)"})
        left = await api.workspace_list({"directory": str(root)})
        original = await api.flow_open({"flow": "churn"})
        copy = await api.flow_open({"flow": "churn (copy)"})

    assert duplicated == {
        "flow": "churn (copy)",
        "path": str(root / "churn (copy).flow"),
    }
    assert (root / "churn.flow").exists()
    assert (root / "churn (copy).flow").exists()
    assert sorted(flow["relative_path"] for flow in left["flows"]) == [
        "churn (copy).flow",
        "churn.flow",
        "sales.flow",
    ]
    assert [cell["slug"] for cell in original["cells"]] == ["score"]
    assert [cell["slug"] for cell in copy["cells"]] == ["score"]


async def test_duplicating_a_flow_onto_an_existing_name_is_refused(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn", "sales"))

    async with daemon_api(root) as api:
        with pytest.raises(FlowAlreadyExists):
            await api.flow_duplicate({"flow": "churn", "name": "sales"})

    assert (root / "churn.flow").exists()
    assert (root / "sales.flow").exists()


async def test_an_unknown_flow_is_refused_by_name(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=("churn",))

    async with daemon_api(root) as api:
        with pytest.raises(FlowNotFound) as missing:
            await api.flow_open({"flow": "sweep"})

    assert "`sweep`" in str(missing.value) and "`churn`" in str(missing.value)


async def test_no_internals_reach_the_api_surface(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        payload = json.dumps(await api.status({}))
        session = api.hub.session("churn")
        branch_id = session.store.branches.get("main").branch_id
        here = session.store.index.slice_versions(branch_id)

    for uid, version in here.items():
        assert uid not in payload
        assert version.version_id not in payload
        assert version.definition_hash not in payload
    assert "score" in payload


async def test_workspace_files_are_never_versioned_by_a_flow(tmp_path: Path):
    root = make_workspace(tmp_path / "project", files={"data/raw.csv": "a,b"})
    write_cell(root / "churn.flow", "score", SCORE_CELL)
    write_file(root / "helpers.py", "VALUE = 1")

    async with daemon_api(root) as api:
        opened = await api.flow_open({"flow": "churn"})

    assert slugs(opened) == ["score"]


def _definition_hashes(session: FlowSession) -> dict[str, str]:
    return {
        slug: version.definition_hash
        for slug, version in slice_of(session, "main").items()
    }


def _memo_keys(session: FlowSession) -> dict[str, str]:
    here = queries.read(session, "main")
    return {here.versions[uid].slug: mat.memo_key for uid, mat in here.mats.items()}


def _kernel_state(payload: dict[str, Any]) -> tuple[str, bool, list[str]]:
    """Whether a kernel is running and whether it is behind the lockfile."""
    kernel = payload["kernel"]
    return kernel["state"], kernel["restart_required"], kernel["behind"]
