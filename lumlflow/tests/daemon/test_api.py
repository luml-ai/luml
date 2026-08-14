"""The daemon API over a real workspace: browse, init, open, run, delete.

The end-to-end run here is the whole stack — a cell file goes through
acceptance, the scheduler plans it, a kernel process materializes it, and the
store records it — on a workspace holding two flows, because a workspace daemon
that hosts one flow proves nothing about the one that hosts two.
"""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from lumlflow.flow.daemon import queries
from lumlflow.flow.daemon.hub import FlowSession
from lumlflow.flow.errors import FlowNotFound
from lumlflow.flow.store.flowstore import store_dir
from lumlflow.flow.store.models import RunRecorded

from tests.daemon.helpers import (
    BROKEN_CELL,
    FRAME_CELL,
    REPORT_CELL,
    SCORE_CELL,
    daemon_api,
    flow_named,
    make_workspace,
    ops_of,
    slice_of,
    slugs,
    transactions,
    values_in,
    write_cell,
    write_file,
)


async def test_the_browser_sees_flows_as_documents_and_files_as_context(
    tmp_path: Path,
):
    root = make_workspace(
        tmp_path / "project", flows=("churn",), files={"helpers.py": "VALUE = 1"}
    )
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        listed = await api.workspace_list({})

    assert [(entry["name"], entry["kind"]) for entry in listed["entries"]] == [
        ("churn.flow", "flow"),
        ("helpers.py", "file"),
    ]


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


async def test_the_browser_climbs_out_of_the_workspace_and_opens_what_it_finds(
    tmp_path: Path,
):
    """The launch directory is where browsing starts, not where it ends.

    A flow a neighbouring project holds is one entry with the same one gesture,
    and opening it addresses the flow by where it is — so the workbench link is
    a link, not an instruction to relaunch somewhere else.
    """
    root = make_workspace(tmp_path / "project")
    sales = make_workspace(tmp_path / "other", flows=("sales",)) / "sales.flow"
    write_cell(sales, "score", SCORE_CELL)

    async with daemon_api(root) as api:
        above = await api.workspace_list({"path": str(tmp_path)})
        sideways = await api.workspace_list({"path": str(tmp_path / "other")})
        found = next(entry for entry in sideways["entries"] if entry["kind"] == "flow")
        opened = await api.flow_open({"flow": found["path"]})
        ran = await api.run({"flow": found["path"], "target": "score"})

    # The launch directory is still what `root` names; only the listing moved.
    assert (above["outside"], above["root"]) == (True, str(root))
    assert found["path"] == str(sales)
    # The brief spells the flow the way the browser addressed it, which is what
    # every frame on the journal channel is keyed by.
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
        hosted = {ref.name: api.hub.open(ref).workspace_dir for ref in api.hub.flows()}

    assert ran["executed"] == ["where"]
    assert session.workspace_dir == other
    assert values_in(other / "sales.flow") == [{"marker": 2}]
    # And nothing moved under the flows the launch directory does contain.
    assert hosted == {"churn": root}


async def test_flow_init_scaffolds_a_store_and_leaves_the_flow_unbound(tmp_path: Path):
    root = make_workspace(tmp_path / "project", flows=())

    async with daemon_api(root) as api:
        created = await api.flow_init({"name": "churn"})
        listed = await api.workspace_list({})
        # The API path creates a flow, never a checkout: binding the worktree
        # and projecting `main` into `cells/` is what `lumlflow init` adds.
        bound = api.hub.session("churn").store.branches.bound_branch()

    assert created["flow"] == "churn"
    assert created["path"] == "churn.flow"
    assert created["branch"] == "main"
    assert _kernel_state(created) == ("stopped", False, [])
    assert store_dir(root / "churn.flow").is_dir()
    # The flow, and the `AGENTS.md` the daemon generates beside it.
    assert [(entry["name"], entry["kind"]) for entry in listed["entries"]] == [
        ("churn.flow", "flow"),
        ("AGENTS.md", "file"),
    ]
    assert bound is None


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
        "env_policy": "ask",
    }
    assert relaxed["settings"]["reactivity"] == "lazy"
    # The runtime's own settings are not a panel's to show.
    assert "sandbox" not in opened["settings"]
    assert "paranoid" not in opened["settings"]


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


async def test_a_failing_cell_is_recorded_not_raised(tmp_path: Path):
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", BROKEN_CELL)

    async with daemon_api(root) as api:
        outcome = await api.run({"flow": "churn", "target": "score"})
        opened = await api.flow_open({"flow": "churn"})

    assert outcome["failed"] == "score"
    assert outcome["executed"] == []
    assert slugs(opened, "failed") == ["score"]


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


async def test_browsing_a_materialized_flow_starts_no_kernel(tmp_path: Path):
    """Everything a session renders is stored, so a browser that never runs a
    cell never spawns a process — the expand gesture is what starts one."""
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "score", SCORE_CELL)

    async with daemon_api(root) as api:
        await api.run({"flow": "churn", "target": "score"})
        await api.hub.session("churn").kernel.stop()

        listed = await api.workspace_list({})
        opened = await api.flow_open({"flow": "churn"})
        status = await api.status({})

    assert [entry["name"] for entry in listed["entries"]] == [
        "churn.flow",
        "AGENTS.md",
    ]
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
        left = await api.workspace_list({})

    assert deleted == {"deleted": "churn", "path": "churn.flow"}
    assert not (root / "churn.flow").exists()
    assert [entry["name"] for entry in left["entries"]] == ["sales.flow", "AGENTS.md"]


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
    """Whether a kernel is running and whether it is behind the lockfile. What
    confines it is reported beside these and asserted in `test_safety.py`."""
    kernel = payload["kernel"]
    return kernel["state"], kernel["restart_required"], kernel["behind"]
