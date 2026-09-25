from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from luml import __version__ as SDK_VERSION
from luml.experiments.tracker import ExperimentTracker
from lumlflow.flow.daemon import kernel_proc, queries
from lumlflow.flow.daemon.api import Api
from lumlflow.flow.store.models import RunRecorded, TrackerRef
from lumlflow.tracker import ThreadSafeTracker, TrackerProvider

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

    def materialize(self, ctx):
        ctx.tracker.log_metric("rmse", 0.4)
        return {"metrics": ctx.tracker.record}
"""

REPORT_CELL = """
class Report:
    consumes = {"metrics": "evaluate.metrics"}
    produces = {"summary": "asset"}

    def materialize(self, ctx, metrics):
        return {"summary": {"rmse": metrics.metrics["rmse"]}}
"""

EDITED_REPORT_CELL = """
class Report:
    consumes = {"metrics": "evaluate.metrics"}
    produces = {"summary": "asset"}

    def materialize(self, ctx, metrics):
        return {"summary": {"score": 1 - metrics.metrics["rmse"]}}
"""

TRACKED_AND_ASSET_CELL = """
class Evaluate:
    produces = {"metrics": "experiment", "score": "asset"}

    def materialize(self, ctx):
        ctx.tracker.log_metric("rmse", 0.4)
        return {"metrics": ctx.tracker.record, "score": 0.6}
"""

EDITED_TRACKED_AND_ASSET_CELL = """
class Evaluate:
    produces = {"metrics": "experiment", "score": "asset"}

    def materialize(self, ctx):
        ctx.tracker.log_metric("rmse", 0.3)
        return {"metrics": ctx.tracker.record, "score": 0.7}
"""

ASSET_REPORT_CELL = """
class Report:
    consumes = {"score": "evaluate.score"}
    produces = {"summary": "asset"}

    def materialize(self, ctx, score):
        return {"summary": {"score": score}}
"""


def _cell(listed: dict[str, Any], slug: str) -> dict[str, Any]:
    return next(cell for cell in listed["cells"] if cell["slug"] == slug)


def _tracker_ref(api: Api, slug: str = "evaluate") -> TrackerRef:
    session = api.hub.session("churn")
    branch_id = session.store.branches.get("main").branch_id
    versions = session.store.index.slice_versions(branch_id)
    uid = next(uid for uid, version in versions.items() if version.slug == slug)
    mat_id = session.store.index.baselines(branch_id)[uid]
    mat = session.store.index.materialization(mat_id)
    assert mat is not None
    ref = mat.outputs["metrics"].tracker_ref
    assert ref is not None
    return ref


@asynccontextmanager
async def _materialized_flow(
    tmp_path: Path, tracker: TrackerProvider
) -> AsyncIterator[tuple[Path, Api]]:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", TRACKED_CELL)
    write_cell(root / "churn.flow", "report", REPORT_CELL)
    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})
        yield root, api


async def test_an_unreadable_tracker_store_is_a_renderable_state(
    tmp_path: Path,
    tracker: TrackerProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(kernel_proc, "DAEMON_SDK_VERSION", "0.0.0")
    async with _materialized_flow(tmp_path, tracker) as (root, api):
        session = api.hub.session("churn")
        ref = _tracker_ref(api)
        assert queries.experiment_state(session, ref).state == "ok"
        session.experiment_states.clear()

        def unreadable(_experiment_id: str) -> Any:
            raise RuntimeError("store schema was written by luml-sdk 99.0")

        monkeypatch.setattr(tracker, "read_experiment", unreadable)
        state = queries.experiment_state(session, ref)
        shown = await api.cells_show({"flow": "churn", "slug": "evaluate"})
        previewed = await api.asset_preview(
            {"flow": "churn", "target": "evaluate.metrics"}
        )

        assert state.state == "unreachable"
        assert str(tracker.store_path) in state.sentence
        assert "luml-sdk 99.0" in state.sentence
        assert f"uses {SDK_VERSION}" in state.sentence
        assert "upgrade lumlflow" in state.sentence
        assert shown["state"] == "synced"
        assert shown["tracker"] == previewed["tracker"]
        assert shown["tracker"]["state"] == "unreachable"
        assert shown["tracker"]["url"] is None
        assert shown["tracker"]["store"] == str(tracker.store_path)
        assert shown["tracker"]["sentence"] == state.sentence
        assert ops_of(session, RunRecorded)[-1].state == "succeeded"
        assert root.exists()


async def test_an_experiment_from_a_different_store_is_unreachable(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    async with _materialized_flow(tmp_path, tracker) as (root, first_api):
        ref = _tracker_ref(first_api)

    other_store = tmp_path / "other-experiments"
    other = TrackerProvider(lambda: other_store)
    with other.bind(ThreadSafeTracker(f"sqlite://{other_store}")):
        async with daemon_api(root, tracker=other) as api:
            await api.flow_open({"flow": "churn"})
            state = queries.experiment_state(api.hub.session("churn"), ref)
            shown = await api.cells_show({"flow": "churn", "slug": "evaluate"})

    assert state.state == "unreachable"
    assert f"different tracker store (`{ref.store}`)" in state.sentence
    assert "lumlflow daemon stop" in state.sentence
    assert shown["state"] == "synced"
    assert shown["tracker"]["sentence"] == state.sentence


async def test_an_external_delete_expires_and_flow_open_drops_the_cache(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    async with _materialized_flow(tmp_path, tracker) as (_root, api):
        session = api.hub.session("churn")
        ref = _tracker_ref(api)
        assert queries.experiment_state(session, ref).state == "ok"

        external = ExperimentTracker(f"sqlite://{tracker.store_path}")
        external.delete_experiment(ref.experiment_id)
        assert queries.experiment_state(session, ref).state == "ok"

        session.experiment_states.max_age_s = 0
        assert queries.experiment_state(session, ref).state == "missing"
        missing = await api.cells_list({"flow": "churn"})
        tracked = _cell(missing, "evaluate")["tracker"]
        assert tracked["state"] == "missing"
        assert tracked["url"] is None
        assert tracked["tags"] == ["main", "evaluate"]
        assert tracked["recorded_step"] is not None

        await api.run({"flow": "churn", "target": "evaluate"})
        replacement = _tracker_ref(api)
        session.experiment_states.max_age_s = 60
        assert queries.experiment_state(session, replacement).state == "ok"
        external.delete_experiment(replacement.experiment_id)

        await api.flow_open({"flow": "churn"})
        assert queries.experiment_state(session, replacement).state == "missing"


async def test_auto_declines_a_stale_consumer_of_a_removed_experiment(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    async with _materialized_flow(tmp_path, tracker) as (_root, api):
        session = api.hub.session("churn")
        ref = _tracker_ref(api)
        run_count = len(ops_of(session, RunRecorded))
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await session.reactor.settled()

        tracker.delete_experiment(ref.experiment_id)
        before_edit = len(transactions(session))
        await api.cells_edit(
            {"flow": "churn", "slug": "report", "source": EDITED_REPORT_CELL}
        )
        await session.reactor.settled()
        listed = await api.cells_list({"flow": "churn"})
        decline = _cell(listed, "report")["auto_declined"]

        assert len(ops_of(session, RunRecorded)) == run_count
        assert len(transactions(session)) == before_edit + 1
        assert decline["reason"] == "dangling-experiment"
        assert "evaluate" in decline["detail"]
        assert "removed experiment" in decline["detail"]

        preflight = await api.preflight({"flow": "churn", "target": "report"})
        assert preflight["recompute"] == ["evaluate", "report"]
        assert len(preflight["reasons"]) == 1
        assert "evaluate" in preflight["reasons"][0]
        assert ref.experiment_id in preflight["reasons"][0]

        outcome = await api.run({"flow": "churn", "target": "report"})
        assert outcome["executed"] == ["evaluate", "report"]


async def test_auto_declines_an_indirect_run_of_a_dangling_experiment_producer(
    tmp_path: Path, tracker: TrackerProvider
) -> None:
    root = make_workspace(tmp_path / "project")
    write_cell(root / "churn.flow", "evaluate", TRACKED_AND_ASSET_CELL)
    write_cell(root / "churn.flow", "report", ASSET_REPORT_CELL)
    async with daemon_api(root, tracker=tracker) as api:
        await api.flow_open({"flow": "churn"})
        await api.run({"flow": "churn", "target": "report"})
        session = api.hub.session("churn")
        ref = _tracker_ref(api)
        await api.settings_set(
            {"flow": "churn", "reactivity": "auto", "eager_cost_threshold_s": 60}
        )
        await session.reactor.settled()

        tracker.delete_experiment(ref.experiment_id)
        run_count = len(ops_of(session, RunRecorded))
        before_edit = len(transactions(session))
        await api.cells_edit(
            {
                "flow": "churn",
                "slug": "evaluate",
                "source": EDITED_TRACKED_AND_ASSET_CELL,
            }
        )
        await session.reactor.settled()
        listed = await api.cells_list({"flow": "churn"})
        decline = _cell(listed, "report")["auto_declined"]

        assert len(ops_of(session, RunRecorded)) == run_count
        assert len(transactions(session)) == before_edit + 1
        assert decline["reason"] == "dangling-experiment"
        assert "evaluate" in decline["detail"]
        assert "removed experiment" in decline["detail"]
