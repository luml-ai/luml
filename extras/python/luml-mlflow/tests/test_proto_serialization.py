"""Proto-serialization regression tests for the luml tracking store.

The MLflow server serializes every entity the store returns (``to_proto()``)
before handing it to the UI/REST layer. The store's other tests read entity
fields directly and never serialize, so a field carrying the wrong shape — e.g.
``RunInfo.status`` as the proto integer instead of the canonical status string —
passes those value-only assertions yet breaks the UI: ``RunInfo.to_proto()``
routes ``status`` through ``RunStatus.from_string`` and rejects integers.

These tests reproduce exactly what the server does — serialize every returned
``Run``/``Experiment``/``Metric`` — and lock in that all status-resolution paths
yield a canonical status string.
"""

from pathlib import Path

import pytest
from luml_mlflow.meta import RUN_STATUS, write_run_info_field
from luml_mlflow.store import LumlTrackingStore
from mlflow.entities import Experiment, Metric, Param, Run, RunStatus, RunTag


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    # Local-only target: no network, and terminal updates skip auto-sync.
    return LumlTrackingStore("luml://local")


def _log_run(
    store: LumlTrackingStore,
    *,
    experiment_id: str,
    run_name: str,
    final_status: int | None = None,
) -> str:
    """Drive a run through a realistic logging lifecycle, return its run id."""
    run = store.create_run(
        experiment_id=experiment_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name=run_name,
    )
    run_id = run.info.run_id
    store.log_param(run_id, Param("lr", "0.01"))
    store.set_tag(run_id, RunTag("approved", "true"))
    store.set_tag(run_id, RunTag("mlflow.runName", run_name))
    for step, value in enumerate((0.5, 0.3, 0.2)):
        store.log_metric(
            run_id, Metric(key="loss", value=value, timestamp=0, step=step)
        )
    if final_status is not None:
        store.update_run_info(
            run_id, run_status=final_status, end_time=1000, run_name=None
        )
    return run_id


# Each case: (final_status passed to update_run_info, canonical status string).
RUN_STATES = [
    pytest.param(None, "RUNNING", id="active"),
    pytest.param(RunStatus.FINISHED, "FINISHED", id="finished"),
    pytest.param(RunStatus.FAILED, "FAILED", id="failed"),
]


@pytest.mark.parametrize(("final_status", "expected"), RUN_STATES)
def test_get_run_serializes_with_canonical_status(
    store: LumlTrackingStore, final_status: int | None, expected: str
) -> None:
    exp_id = store.create_experiment("fraud")
    run_id = _log_run(
        store, experiment_id=exp_id, run_name="r", final_status=final_status
    )

    run = store.get_run(run_id)
    # The server's get-run handler serializes then the client deserializes.
    roundtripped = Run.from_proto(run.to_proto())
    assert roundtripped.info.status == expected


@pytest.mark.parametrize(("final_status", "expected"), RUN_STATES)
def test_status_is_canonical_string(
    store: LumlTrackingStore, final_status: int | None, expected: str
) -> None:
    exp_id = store.create_experiment("fraud")
    run_id = _log_run(
        store, experiment_id=exp_id, run_name="r", final_status=final_status
    )

    status = store.get_run(run_id).info.status
    assert isinstance(status, str)
    assert status == expected
    # Accepted by RunStatus.from_string — the call RunInfo.to_proto makes.
    assert RunStatus.from_string(status) == RunStatus.from_string(expected)


def test_search_runs_all_serialize(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    _log_run(store, experiment_id=exp_id, run_name="active")
    _log_run(
        store, experiment_id=exp_id, run_name="done", final_status=RunStatus.FINISHED
    )
    _log_run(
        store, experiment_id=exp_id, run_name="bad", final_status=RunStatus.FAILED
    )

    runs = list(
        store.search_runs(
            experiment_ids=[exp_id],
            filter_string="",
            run_view_type=1,
            max_results=100,
        )
    )
    assert len(runs) == 3
    # The server's search handler calls to_proto() on every run.
    statuses = {Run.from_proto(r.to_proto()).info.status for r in runs}
    assert statuses == {"RUNNING", "FINISHED", "FAILED"}


def test_metadata_status_override_wins_and_round_trips(
    store: LumlTrackingStore,
) -> None:
    exp_id = store.create_experiment("fraud")
    # Active run (SDK status has no terminal value yet).
    run_id = _log_run(store, experiment_id=exp_id, run_name="r")
    # A metadata override with no SDK equivalent must still win and survive proto.
    write_run_info_field(store._tracker, run_id, RUN_STATUS, "KILLED")

    run = store.get_run(run_id)
    assert run.info.status == "KILLED"
    assert Run.from_proto(run.to_proto()).info.status == "KILLED"


def test_experiments_serialize(store: LumlTrackingStore) -> None:
    a = store.create_experiment("a")
    store.create_experiment("b")

    experiments = list(store.search_experiments())
    assert experiments  # includes the auto-created Default plus a, b
    for exp in experiments:
        roundtripped = Experiment.from_proto(exp.to_proto())
        assert roundtripped.experiment_id == exp.experiment_id

    fetched = store.get_experiment(a)
    assert Experiment.from_proto(fetched.to_proto()).name == "a"


def test_metric_history_serializes(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    run_id = _log_run(store, experiment_id=exp_id, run_name="r")

    history = list(store.get_metric_history(run_id, "loss"))
    assert len(history) == 3
    for metric in history:
        roundtripped = Metric.from_proto(metric.to_proto())
        assert roundtripped.key == "loss"
    assert [Metric.from_proto(m.to_proto()).value for m in history] == [0.5, 0.3, 0.2]
