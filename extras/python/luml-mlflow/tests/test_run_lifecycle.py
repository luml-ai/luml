"""Soft-delete and restore semantics for MLflow runs.

MLflow's ``delete_run`` is a reversible soft delete: the run keeps its data but
is hidden from default searches. These tests pin that contract onto the luml
store, including the ``run_view_type`` filtering that makes it observable.
"""

from pathlib import Path

import pytest
from luml_mlflow.store import LumlTrackingStore
from mlflow.entities import LifecycleStage, ViewType
from mlflow.exceptions import MlflowException


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
