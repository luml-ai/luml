import asyncio
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from luml import __version__ as SDK_VERSION
from lumlflow.flow.daemon import kernel_proc
from lumlflow.flow.errors import FlowError
from lumlflow.flow.store.models import CellNoted, MemoHit, RunRecorded
from lumlflow.tracker import TrackerProvider

from tests.daemon.helpers import (
    daemon_api,
    make_workspace,
    ops_of,
    transactions,
    write_cell,
)

TRACKED_CELL = """
class Evaluate:
    produces = {"metrics": "experiment"}
    params = {"folds": 5}

    def materialize(self, ctx):
        ctx.tracker.log_param("alpha", 0.25)
        ctx.tracker.log_metric("rmse", 0.4, step=3)
        return {"metrics": ctx.tracker.record}
"""

FAILED_CELL = """
class Evaluate:
    produces = {"metrics": "experiment"}

    def materialize(self, ctx):
        ctx.tracker.log_metric("rmse", 0.9)
        raise RuntimeError("evaluation failed")
"""

TWO_EXPERIMENTS_CELL = """
class Evaluate:
    produces = {"first": "experiment", "second": "experiment"}

    def materialize(self, ctx):
        (ctx.workspace_dir / "cell-ran").write_text("ran")
        return {"first": ctx.tracker.record, "second": ctx.tracker.record}
"""

KILLS_KERNEL_CELL = """
class Evaluate:
    produces = {"metrics": "experiment"}

    def materialize(self, ctx):
        import os

        ctx.tracker.log_metric("rmse", 0.7, step=1)
        os._exit(17)
"""

CANCELLED_CELL = """
class Evaluate:
    produces = {"metrics": "experiment"}

    def materialize(self, ctx):
        import time

        ctx.tracker.log_metric("rmse", 0.8, step=1)
        (ctx.workspace_dir / "metric-logged").touch()
        while True:
            time.sleep(0.01)
"""

REPORT_CELL = """
class Report:
    consumes = {"metrics": "evaluate.metrics"}
    produces = {"summary": "asset"}

    def materialize(self, ctx, metrics):
        return {"summary": "ready"}
"""


async def test_materialized_experiment_records_identity_and_tracker_ref(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "evaluate", TRACKED_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        outcome = await api.run({"flow": "churn", "target": "evaluate"})
        (run,) = ops_of(session, RunRecorded)
        (version,) = session.store.index.slice_versions(
            session.store.branches.get("main").branch_id
        ).values()
        listed = await api.cells_list({"flow": "churn"})
        shown = await api.cells_show({"flow": "churn", "slug": "evaluate"})
        previewed = await api.asset_preview(
            {"flow": "churn", "target": "evaluate.metrics"}
        )

    experiment = _only_experiment(tracker)
    identity = experiment.metadata["lumlflow"]
    tracker_view = {
        "id": experiment.id,
        "group": "churn",
        "state": "ok",
        "url": f"/experiments/{experiment.group_id}/{experiment.id}",
        "store": str(tracker.store_path),
        "tags": ["main", "evaluate"],
        "sentence": "",
        "recorded_step": run.finished_step,
    }
    assert outcome["executed"] == ["evaluate"]
    assert run.experiment_id == experiment.id
    assert run.experiment_store == str(tracker.store_path)
    assert run.outputs["metrics"].tracker_ref is not None
    assert run.outputs["metrics"].tracker_ref.experiment_id == experiment.id
    assert run.outputs["metrics"].tracker_ref.group == "churn"
    assert run.outputs["metrics"].tracker_ref.store == str(tracker.store_path)
    assert run.outputs["metrics"].tracker_ref.tags == ["main", "evaluate"]
    assert listed["cells"][0]["tracker"] == tracker_view
    assert shown["tracker"] == tracker_view
    assert previewed["tracker"] == tracker_view
    assert identity == {
        "flow": "churn",
        "flow_id": session.store.manifest.flow_id,
        "path": str(flow_dir.resolve()),
        "slug": "evaluate",
        "uid": version.uid,
        "lane": "main",
        "version_id": version.version_id,
        "run_id": identity["run_id"],
    }
    assert identity["run_id"]


async def test_failed_run_and_cell_show_keep_the_experiment_id(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", FAILED_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        outcome = await api.run({"flow": "churn", "target": "evaluate"})
        session = api.hub.session("churn")
        (run,) = ops_of(session, RunRecorded)
        shown = await api.cells_show({"flow": "churn", "slug": "evaluate"})

    experiment = _only_experiment(tracker)
    assert outcome["failed"] == "evaluate"
    assert run.state == "failed"
    assert run.outputs == {}
    assert run.experiment_id == experiment.id
    assert run.experiment_store == str(tracker.store_path)
    assert shown["tracker"] == {
        "id": experiment.id,
        "group": "churn",
        "state": "ok",
        "url": f"/experiments/{experiment.group_id}/{experiment.id}",
        "store": str(tracker.store_path),
        "tags": ["main", "evaluate"],
        "sentence": "",
        "recorded_step": run.finished_step,
    }
    assert experiment.status == "error"


async def test_two_experiment_outputs_are_refused_before_the_kernel_starts(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    marker = root / "cell-ran"
    write_cell(root / "churn.flow", "evaluate", TWO_EXPERIMENTS_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        with pytest.raises(FlowError, match="exactly one.*experiment"):
            await api.run({"flow": "churn", "target": "evaluate"})

        assert session.kernel.state == "stopped"
        assert ops_of(session, RunRecorded) == []

    assert tracker.list_experiments() == []
    assert not marker.exists()


async def test_failed_experiment_close_keeps_the_materialization_and_adds_a_note(
    tmp_path: Path,
    tracker: TrackerProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", TRACKED_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        session = api.hub.session("churn")
        result = session.kernel._result

        def with_close_failure(record: dict[str, Any], started: Any) -> Any:
            return replace(
                result(record, started),
                experiment_close_error="could not close the experiment",
            )

        monkeypatch.setattr(session.kernel, "_result", with_close_failure)
        outcome = await api.run({"flow": "churn", "target": "evaluate"})
        shown = await api.cells_show({"flow": "churn", "slug": "evaluate"})
        lines = transactions(session)

    assert outcome["executed"] == ["evaluate"]
    assert [run.state for run in ops_of(session, RunRecorded)] == ["succeeded"]
    notes = ops_of(session, CellNoted)
    assert len(notes) == 1
    assert notes[0].kind == "experiment_unclosed"
    assert notes[0].sentence == "could not close the experiment"
    assert lines[-1].actor == "system"
    assert lines[-1].branch is not None
    assert shown["state"] == "synced"
    assert shown["notes"][-1]["kind"] == "experiment_unclosed"
    assert shown["notes"][-1]["sentence"] == "could not close the experiment"


async def test_a_kernel_death_fails_its_orphaned_experiment_and_records_the_run(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", KILLS_KERNEL_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        outcome = await api.run({"flow": "churn", "target": "evaluate"})
        session = api.hub.session("churn")
        (run,) = ops_of(session, RunRecorded)

    experiment = _only_experiment(tracker)
    history = tracker.get_experiment_metric_history(experiment.id, "rmse")
    assert outcome["failed"] == "evaluate"
    assert run.state == "failed"
    assert run.experiment_id == experiment.id
    assert experiment.status == "error"
    assert [(point["value"], point["step"]) for point in history] == [(0.7, 1)]


async def test_a_cancelled_run_keeps_its_live_experiment_reference(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", CANCELLED_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        running = asyncio.create_task(api.run({"flow": "churn", "target": "evaluate"}))
        await _wait_until((root / "metric-logged").exists)
        experiment_id = _only_experiment(tracker).id
        history = tracker.get_experiment_metric_history(experiment_id, "rmse")
        listed = await asyncio.wait_for(api.cells_list({"flow": "churn"}), timeout=2)

        cancelled = await api.cancel({"flow": "churn"})
        outcome = await asyncio.wait_for(running, timeout=30)
        session = api.hub.session("churn")
        await _wait_until(lambda: not session.queue.busy)
        (run,) = ops_of(session, RunRecorded)

    experiment = _only_experiment(tracker)

    assert listed["cells"][0]["slug"] == "evaluate"
    assert [(point["value"], point["step"]) for point in history] == [(0.8, 1)]
    assert cancelled["stopped"] is True
    assert outcome["abandoned"] is True
    assert run.state == "cancelled"
    assert run.experiment_id == experiment_id
    assert experiment.status == "error"


async def test_sdk_version_warning_is_kept_on_the_run_record(
    tmp_path: Path,
    tracker: TrackerProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", TRACKED_CELL)
    daemon_version = "999.0.0"
    monkeypatch.setattr(kernel_proc, "DAEMON_SDK_VERSION", daemon_version)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "evaluate"})
        session = api.hub.session("churn")
        (run,) = ops_of(session, RunRecorded)
        shown = await api.cells_show({"flow": "churn", "slug": "evaluate"})

    assert run.sdk_version_warning is not None
    assert SDK_VERSION in run.sdk_version_warning
    assert daemon_version in run.sdk_version_warning
    assert shown["sdk_version_warning"] == run.sdk_version_warning


async def test_experiment_memo_hit_creates_nothing_and_reuses_the_ref(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", TRACKED_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        await api.fork({"flow": "churn", "name": "exp"})
        await api.run({"flow": "churn", "target": "evaluate"})
        experiment = _only_experiment(tracker)

        outcome = await api.run(
            {"flow": "churn", "branch": "exp", "target": "evaluate"}
        )
        session = api.hub.session("churn")
        shown = await api.cells_show(
            {"flow": "churn", "branch": "exp", "slug": "evaluate"}
        )
        (run,) = ops_of(session, RunRecorded)

    assert outcome["cached"] == ["evaluate"]
    assert len(ops_of(session, MemoHit)) == 1
    assert len(tracker.list_experiments()) == 1
    assert run.outputs["metrics"].tracker_ref is not None
    assert run.outputs["metrics"].tracker_ref.experiment_id == experiment.id
    assert shown["tracker"]["id"] == experiment.id
    assert shown["tracker"]["tags"] == ["main", "evaluate"]


async def test_identical_experiment_snapshots_keep_consumers_synced(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    flow_dir = root / "churn.flow"
    write_cell(flow_dir, "evaluate", TRACKED_CELL)
    write_cell(flow_dir, "report", REPORT_CELL)

    async with daemon_api(root, tracker=tracker) as api:
        first = await api.run({"flow": "churn", "target": "report"})
        rerun = await api.run({"flow": "churn", "target": "evaluate", "force": True})
        shown = await api.cells_show({"flow": "churn", "slug": "report"})
        session = api.hub.session("churn")
        runs = ops_of(session, RunRecorded)

    assert first["executed"] == ["evaluate", "report"]
    assert rerun["executed"] == ["evaluate"]
    assert len(tracker.list_experiments()) == 2
    assert len(runs) == 3
    assert shown["state"] == "synced"


def test_spawn_environment_names_the_tracker_store_and_daemon_sdk_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "project"
    store = tmp_path / "experiments"
    workspace.mkdir()
    monkeypatch.delenv("BACKEND_STORE_URI", raising=False)
    monkeypatch.delenv("LUML_BACKEND_STORE_URI", raising=False)
    monkeypatch.delenv("LUMLFLOW_DAEMON_SDK_VERSION", raising=False)

    environment = kernel_proc.spawn_environment(workspace, tracker_store=store)

    assert environment["BACKEND_STORE_URI"] == str(store.resolve())
    assert environment["LUML_BACKEND_STORE_URI"] == str(store.resolve())
    assert environment["LUMLFLOW_DAEMON_SDK_VERSION"] == SDK_VERSION


def _only_experiment(tracker: TrackerProvider) -> Any:
    experiments = tracker.list_experiments()
    assert len(experiments) == 1
    experiment = tracker.get_experiment_record(experiments[0].id)
    assert experiment is not None
    return experiment


async def _wait_until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(30):
        while not condition():
            await asyncio.sleep(0.01)
