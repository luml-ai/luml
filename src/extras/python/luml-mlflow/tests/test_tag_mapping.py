"""Tests for the four-bucket tag-mapping rule and run reconstruction.

Covers the rule documented in ``SPEC.md`` / ``meta.py``:

* ``luml.*`` → write rejected via the shared ``unsupported`` handler.
* ``mlflow.*`` → stored on the ``metadata`` column silently; round-trips
  faithfully.
* Flag-shaped (``"true"``/``""``) → flat SDK ``tags`` flags, lossless.
* Other user tags → ``log_static`` + warning, no round-trip.
"""

from pathlib import Path

import pytest
from luml_mlflow.meta import (
    LUML_UPLOAD_STATUS,
    UPLOAD_STATUS_NOT_UPLOADED,
)
from luml_mlflow.store import LumlTrackingStore
from mlflow.entities import Metric, Param, RunTag


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


def _start_run(store: LumlTrackingStore) -> str:
    exp_id = store.create_experiment("fraud")
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r1",
    )
    return run.info.run_id


# ---------------------------------------------------------------- flag-shaped


def test_flag_tag_with_true_round_trips_losslessly(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    store.set_tag(run_id, RunTag("approved", "true"))
    run = store.get_run(run_id)
    assert run.data.tags["approved"] == "true"


def test_flag_tag_with_empty_round_trips_losslessly(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    store.set_tag(run_id, RunTag("reviewed", ""))
    run = store.get_run(run_id)
    assert run.data.tags["reviewed"] == ""


def test_flag_tags_distinguish_true_from_empty(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    store.set_tag(run_id, RunTag("approved", "true"))
    store.set_tag(run_id, RunTag("reviewed", ""))
    run = store.get_run(run_id)
    assert run.data.tags["approved"] == "true"
    assert run.data.tags["reviewed"] == ""


def test_flag_tag_lands_in_sdk_flat_tags(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    store.set_tag(run_id, RunTag("approved", "true"))
    record = store._tracker.get_experiment_record(run_id)
    assert record is not None
    # Encoded form for "true" is the bare key; for "" it would be "key=".
    assert "approved" in (record.tags or [])


# ---------------------------------------------------------- non-flag user tag


def test_non_flag_user_tag_becomes_static_param_with_warning(
    store: LumlTrackingStore, caplog: pytest.LogCaptureFixture
) -> None:
    run_id = _start_run(store)
    with caplog.at_level("WARNING"):
        store.set_tag(run_id, RunTag("stage", "prod"))
    assert any("stage" in r.message for r in caplog.records)
    run = store.get_run(run_id)
    # Stored as a param.
    assert run.data.params.get("stage") == "prod"
    # Does NOT round-trip as a tag.
    assert "stage" not in run.data.tags


# ----------------------------------------------------------- mlflow.* tags


def test_mlflow_tag_round_trips_silently(
    store: LumlTrackingStore, caplog: pytest.LogCaptureFixture
) -> None:
    run_id = _start_run(store)
    with caplog.at_level("WARNING"):
        store.set_tag(run_id, RunTag("mlflow.runName", "renamed"))
        store.set_tag(
            run_id,
            RunTag("mlflow.source.git.commit", "abc123"),
        )
        store.set_tag(run_id, RunTag("mlflow.log-model.history", "[]"))
    # No warnings should be emitted for mlflow.* tags.
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == []
    run = store.get_run(run_id)
    assert run.data.tags["mlflow.runName"] == "renamed"
    assert run.data.tags["mlflow.source.git.commit"] == "abc123"
    assert run.data.tags["mlflow.log-model.history"] == "[]"
    # And they are NOT stored as params.
    assert "mlflow.runName" not in run.data.params


# ----------------------------------------------------------- luml.* reserved


def test_user_set_tag_luml_namespace_warn_ignored(
    store: LumlTrackingStore, caplog: pytest.LogCaptureFixture
) -> None:
    run_id = _start_run(store)
    with caplog.at_level("WARNING"):
        store.set_tag(run_id, RunTag("luml.upload_status", "uploaded"))
    assert any("luml." in r.message for r in caplog.records)
    # Default warn → write is ignored; the dedicated column stays at
    # not_uploaded.
    assert (
        store._tracker.get_experiment_upload_status(run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


def test_user_set_tag_luml_namespace_raise(
    store: LumlTrackingStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from luml_mlflow import config as config_mod
    from mlflow.exceptions import MlflowException

    monkeypatch.setenv("LUML_MLFLOW_ON_UNSUPPORTED", "raise")
    config_mod.reset_settings_cache()
    run_id = _start_run(store)
    with pytest.raises(MlflowException, match="luml."):
        store.set_tag(run_id, RunTag("luml.upload_status", "uploaded"))
    # Internal column is not touched even on the failed path.
    assert (
        store._tracker.get_experiment_upload_status(run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


def test_upload_status_surfaces_as_luml_tag(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    run = store.get_run(run_id)
    assert run.data.tags[LUML_UPLOAD_STATUS] == UPLOAD_STATUS_NOT_UPLOADED


# ---------------------------------------------------------------- params/metrics


def test_log_param_round_trips_via_static_params(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    store.log_param(run_id, Param("lr", "0.01"))
    run = store.get_run(run_id)
    assert run.data.params["lr"] == "0.01"


def test_log_metric_round_trips_via_dynamic_metrics(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    store.log_metric(run_id, Metric(key="auc", value=0.9, timestamp=0, step=1))
    run = store.get_run(run_id)
    assert run.data.metrics["auc"] == 0.9


def test_metric_history_round_trip(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    store.log_metric(run_id, Metric(key="loss", value=0.5, timestamp=0, step=0))
    store.log_metric(run_id, Metric(key="loss", value=0.3, timestamp=0, step=1))
    store.log_metric(run_id, Metric(key="loss", value=0.2, timestamp=0, step=2))
    history = list(store.get_metric_history(run_id, "loss"))
    assert [m.value for m in history] == [0.5, 0.3, 0.2]
    assert [m.step for m in history] == [0, 1, 2]


def test_run_data_metrics_returns_latest_value(
    store: LumlTrackingStore,
) -> None:
    run_id = _start_run(store)
    store.log_metric(run_id, Metric(key="loss", value=0.5, timestamp=0, step=0))
    store.log_metric(run_id, Metric(key="loss", value=0.2, timestamp=0, step=2))
    run = store.get_run(run_id)
    assert run.data.metrics["loss"] == 0.2


# ---------------------------------------------------------------- log_batch


def test_log_batch_routes_all_kinds(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    store.log_batch(
        run_id,
        params=[Param("lr", "0.01")],
        metrics=[Metric(key="auc", value=0.9, timestamp=0, step=1)],
        tags=[
            RunTag("approved", "true"),
            RunTag("mlflow.runName", "from-batch"),
        ],
    )
    run = store.get_run(run_id)
    assert run.data.params["lr"] == "0.01"
    assert run.data.metrics["auc"] == 0.9
    assert run.data.tags["approved"] == "true"
    assert run.data.tags["mlflow.runName"] == "from-batch"


# ---------------------------------------------------------------- delete_tag


def test_delete_tag_removes_flag(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    store.set_tag(run_id, RunTag("approved", "true"))
    store.delete_tag(run_id, "approved")
    run = store.get_run(run_id)
    assert "approved" not in run.data.tags


def test_delete_tag_removes_mlflow_tag(store: LumlTrackingStore) -> None:
    run_id = _start_run(store)
    store.set_tag(run_id, RunTag("mlflow.runName", "renamed"))
    store.delete_tag(run_id, "mlflow.runName")
    run = store.get_run(run_id)
    assert "mlflow.runName" not in run.data.tags


def test_delete_tag_luml_namespace_rejected(
    store: LumlTrackingStore, caplog: pytest.LogCaptureFixture
) -> None:
    run_id = _start_run(store)
    with caplog.at_level("WARNING"):
        store.delete_tag(run_id, "luml.upload_status")
    assert any("luml." in r.message for r in caplog.records)
    # Internal column remains at not_uploaded.
    assert (
        store._tracker.get_experiment_upload_status(run_id)
        == UPLOAD_STATUS_NOT_UPLOADED
    )


# ---------------------------------------------------------------- terminal


def test_terminal_status_persists_status_string(
    store: LumlTrackingStore,
) -> None:
    from mlflow.entities import RunStatus

    run_id = _start_run(store)
    store.update_run_info(
        run_id, run_status=RunStatus.FINISHED, end_time=1000, run_name=None
    )
    run = store.get_run(run_id)
    assert run.info.status == RunStatus.to_string(RunStatus.FINISHED)


def test_failed_status_persisted(store: LumlTrackingStore) -> None:
    from mlflow.entities import RunStatus

    run_id = _start_run(store)
    store.update_run_info(
        run_id, run_status=RunStatus.FAILED, end_time=1000, run_name=None
    )
    run = store.get_run(run_id)
    assert run.info.status == RunStatus.to_string(RunStatus.FAILED)


# ---------------------------------------------------------------- search runs


def test_search_runs_returns_runs_in_group(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    run1 = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r1",
    )
    run2 = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r2",
    )
    runs = list(
        store.search_runs(
            experiment_ids=[exp_id],
            filter_string="",
            run_view_type=1,
            max_results=100,
        )
    )
    ids = {r.info.run_id for r in runs}
    assert run1.info.run_id in ids
    assert run2.info.run_id in ids


def test_search_runs_excludes_other_experiments(
    store: LumlTrackingStore,
) -> None:
    fraud = store.create_experiment("fraud")
    abuse = store.create_experiment("abuse")
    in_fraud = store.create_run(
        experiment_id=fraud,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="rf",
    )
    in_abuse = store.create_run(
        experiment_id=abuse,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="ra",
    )
    runs = list(
        store.search_runs(
            experiment_ids=[fraud],
            filter_string="",
            run_view_type=1,
            max_results=100,
        )
    )
    ids = {r.info.run_id for r in runs}
    assert in_fraud.info.run_id in ids
    assert in_abuse.info.run_id not in ids


# -------------------------------------------------------- run info reconstruction


def test_user_id_round_trips(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r1",
    )
    fetched = store.get_run(run.info.run_id)
    assert fetched.info.user_id == "alice"


def test_artifact_uri_in_run_info(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r1",
    )
    fetched = store.get_run(run.info.run_id)
    assert fetched.info.artifact_uri.startswith("luml://org1/orbit1")
    assert run.info.run_id in fetched.info.artifact_uri


def test_local_only_marker_round_trips_as_luml_tag(temp_store: Path) -> None:
    local = LumlTrackingStore("luml://local")
    exp_id = local.create_experiment("local_test")
    run = local.create_run(
        experiment_id=exp_id,
        user_id="",
        start_time=0,
        tags=[],
        run_name="local-run",
    )
    fetched = local.get_run(run.info.run_id)
    assert fetched.data.tags.get("luml.local_only") == "true"
