"""Soft-delete and restore semantics for MLflow runs.

MLflow's ``delete_run`` is a reversible soft delete: the run keeps its data but
is hidden from default searches. These tests pin that contract onto the luml
store, including the ``run_view_type`` filtering that makes it observable.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner
from luml_mlflow._tracker import ThreadSafeTracker
from luml_mlflow.meta import RUN_DELETED_TIME, read_run_info_field, write_run_info_field
from luml_mlflow.store import LumlTrackingStore
from mlflow.cli import gc
from mlflow.entities import LifecycleStage, ViewType
from mlflow.exceptions import MlflowException
from mlflow.utils.time import get_current_time_millis


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


def _start_run(store: LumlTrackingStore, name: str = "r") -> tuple[str, str]:
    existing = store.get_experiment_by_name("fraud")
    exp_id = existing.experiment_id if existing else store.create_experiment("fraud")
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name=name,
    )
    return run.info.run_id, exp_id


def _other_process_store(temp_store: Path) -> LumlTrackingStore:
    other = LumlTrackingStore("luml://org1/orbit1")
    other._tracker = ThreadSafeTracker(f"sqlite://{temp_store}")
    return other


def _search_ids(store: LumlTrackingStore, exp_id: str, view_type: int) -> set[str]:
    return {
        run.info.run_id
        for run in store.search_runs(
            experiment_ids=[exp_id],
            filter_string="",
            run_view_type=view_type,
            max_results=100,
        )
    }


def test_delete_run_marks_lifecycle_deleted(store: LumlTrackingStore) -> None:
    run_id, _ = _start_run(store)

    store.delete_run(run_id)

    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.DELETED


def test_deleted_run_is_hidden_from_default_search(
    store: LumlTrackingStore,
) -> None:
    run_id, exp_id = _start_run(store)
    other_id, _ = _start_run(store, "other")

    store.delete_run(run_id)

    assert _search_ids(store, exp_id, ViewType.ACTIVE_ONLY) == {other_id}
    assert _search_ids(store, exp_id, ViewType.DELETED_ONLY) == {run_id}
    assert _search_ids(store, exp_id, ViewType.ALL) == {run_id, other_id}


def test_restore_run_makes_it_active_again(store: LumlTrackingStore) -> None:
    run_id, exp_id = _start_run(store)
    store.delete_run(run_id)

    store.restore_run(run_id)

    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.ACTIVE
    assert run_id in _search_ids(store, exp_id, ViewType.ACTIVE_ONLY)
    assert run_id not in _search_ids(store, exp_id, ViewType.DELETED_ONLY)


def test_delete_run_keeps_run_data(store: LumlTrackingStore) -> None:
    run_id, _ = _start_run(store)
    store._tracker.log_attachment(
        "notes.txt", b"still here", binary=True, experiment_id=run_id
    )

    store.delete_run(run_id)

    assert store._tracker.get_attachment("notes.txt", experiment_id=run_id) == (
        b"still here"
    )


def test_delete_run_is_idempotent(store: LumlTrackingStore) -> None:
    run_id, _ = _start_run(store)

    store.delete_run(run_id)
    store.delete_run(run_id)

    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.DELETED


def test_restore_active_run_is_a_noop(store: LumlTrackingStore) -> None:
    run_id, _ = _start_run(store)

    store.restore_run(run_id)

    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.ACTIVE


def test_delete_run_missing_raises(store: LumlTrackingStore) -> None:
    with pytest.raises(MlflowException, match="not found"):
        store.delete_run("missing-run")


def test_restore_run_missing_raises(store: LumlTrackingStore) -> None:
    with pytest.raises(MlflowException, match="not found"):
        store.restore_run("missing-run")


def test_delete_run_records_deleted_time_and_restore_clears_it(
    store: LumlTrackingStore,
) -> None:
    run_id, _ = _start_run(store)
    before = get_current_time_millis()

    store.delete_run(run_id)

    deleted_time = read_run_info_field(store._tracker, run_id, RUN_DELETED_TIME)
    assert before <= deleted_time <= get_current_time_millis()

    store.restore_run(run_id)

    assert read_run_info_field(store._tracker, run_id, RUN_DELETED_TIME) is None


def test_get_deleted_runs_filters_by_age(store: LumlTrackingStore) -> None:
    run_id, _ = _start_run(store)
    _start_run(store, "active")
    store.delete_run(run_id)

    assert store._get_deleted_runs() == [run_id]
    assert store._get_deleted_runs(older_than=60_000) == []

    write_run_info_field(
        store._tracker, run_id, RUN_DELETED_TIME, get_current_time_millis() - 120_000
    )

    assert store._get_deleted_runs(older_than=60_000) == [run_id]


def test_hard_delete_run_removes_run_and_its_data(store: LumlTrackingStore) -> None:
    run_id, exp_id = _start_run(store)
    store._tracker.log_attachment(
        "notes.txt", b"gone", binary=True, experiment_id=run_id
    )
    store.delete_run(run_id)

    store._hard_delete_run(run_id)

    assert store._tracker.get_experiment_record(run_id) is None
    assert _search_ids(store, exp_id, ViewType.ALL) == set()
    with pytest.raises(MlflowException, match="not found"):
        store.get_run(run_id)


def test_hard_delete_run_refuses_active_run(store: LumlTrackingStore) -> None:
    run_id, _ = _start_run(store)

    with pytest.raises(MlflowException, match="deleted lifecycle stage"):
        store._hard_delete_run(run_id)

    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.ACTIVE


def test_hard_delete_run_refuses_run_restored_after_gc_snapshot(
    store: LumlTrackingStore, temp_store: Path
) -> None:
    run_id, _ = _start_run(store)
    store._tracker.log_attachment(
        "notes.txt", b"kept", binary=True, experiment_id=run_id
    )
    store.delete_run(run_id)
    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.DELETED

    _other_process_store(temp_store).restore_run(run_id)

    with pytest.raises(MlflowException, match="deleted lifecycle stage"):
        store._hard_delete_run(run_id)

    assert store.get_run(run_id).info.lifecycle_stage == LifecycleStage.ACTIVE
    assert store._tracker.get_attachment("notes.txt", experiment_id=run_id) == b"kept"


def test_restore_during_purge_cannot_resurrect_run(
    store: LumlTrackingStore, temp_store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, exp_id = _start_run(store)
    store.delete_run(run_id)
    other = _other_process_store(temp_store)
    purge = store._tracker.delete_experiment
    outcomes: list[str] = []

    def purge_with_concurrent_restore(experiment_id: str) -> None:
        try:
            other.restore_run(experiment_id)
            outcomes.append("restored")
        except MlflowException:
            outcomes.append("refused")
        purge(experiment_id)

    monkeypatch.setattr(
        store._tracker, "delete_experiment", purge_with_concurrent_restore
    )

    store._hard_delete_run(run_id)

    assert outcomes == ["refused"]
    assert store._tracker.get_experiment_record(run_id) is None
    assert _search_ids(other, exp_id, ViewType.ALL) == set()


def test_hard_delete_run_missing_raises(store: LumlTrackingStore) -> None:
    with pytest.raises(MlflowException, match="not found"):
        store._hard_delete_run("missing-run")


def test_mlflow_gc_purges_only_deleted_runs(
    store: LumlTrackingStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "luml://org1/orbit1")
    deleted_id, exp_id = _start_run(store)
    kept_id, _ = _start_run(store, "kept")
    store.delete_run(deleted_id)

    result = CliRunner().invoke(
        gc, ["--backend-store-uri", "luml://org1/orbit1"], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output
    assert f"Run with ID {deleted_id} has been permanently deleted" in result.output
    assert _search_ids(store, exp_id, ViewType.ALL) == {kept_id}


def test_mlflow_gc_older_than_keeps_recent_deletions(
    store: LumlTrackingStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "luml://org1/orbit1")
    run_id, exp_id = _start_run(store)
    store.delete_run(run_id)

    result = CliRunner().invoke(
        gc,
        ["--backend-store-uri", "luml://org1/orbit1", "--older-than", "1d"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert _search_ids(store, exp_id, ViewType.DELETED_ONLY) == {run_id}
