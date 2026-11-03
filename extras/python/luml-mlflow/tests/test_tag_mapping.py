"""Tests for the four-bucket tag-mapping rule and run reconstruction.

Covers the rule documented in ``SPEC.md`` / ``meta.py``:

* ``luml.*`` → write rejected via the shared ``unsupported`` handler.
* ``mlflow.*`` → stored on the ``metadata`` column silently; round-trips
  faithfully.
* Flag-shaped (``"true"``/``""``) → flat SDK ``tags`` flags, lossless.
* Other user tags → metadata, lossless tag round-trip.
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


def test_non_flag_user_tag_round_trips_without_changing_params(
    store: LumlTrackingStore, caplog: pytest.LogCaptureFixture
) -> None:
    run_id = _start_run(store)
    with caplog.at_level("WARNING"):
        store.set_tag(run_id, RunTag("stage", "prod"))
    assert not caplog.records
    run = store.get_run(run_id)
    assert run.data.tags["stage"] == "prod"
    assert "stage" not in run.data.params


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


def _runs_with_accuracy(store: LumlTrackingStore, exp_id: str) -> dict[float, str]:
    out: dict[float, str] = {}
    for acc in (0.5, 0.9, 0.7):
        run = store.create_run(
            experiment_id=exp_id,
            user_id="alice",
            start_time=0,
            tags=[],
            run_name=f"acc-{acc}",
        )
        store.log_metric(run.info.run_id, Metric("acc", acc, 0, 0))
        out[acc] = run.info.run_id
    return out


def test_search_runs_applies_filter_string(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    by_acc = _runs_with_accuracy(store, exp_id)
    runs = store.search_runs(
        experiment_ids=[exp_id],
        filter_string="metrics.acc > 0.6",
        run_view_type=1,
        max_results=100,
    )
    assert {r.info.run_id for r in runs} == {by_acc[0.9], by_acc[0.7]}


def test_search_runs_applies_order_by(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    by_acc = _runs_with_accuracy(store, exp_id)
    runs = store.search_runs(
        experiment_ids=[exp_id],
        filter_string="",
        run_view_type=1,
        max_results=100,
        order_by=["metrics.acc DESC"],
    )
    assert [r.info.run_id for r in runs] == [by_acc[0.9], by_acc[0.7], by_acc[0.5]]


def test_search_runs_paginates(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    by_acc = _runs_with_accuracy(store, exp_id)
    first = store.search_runs(
        experiment_ids=[exp_id],
        filter_string="",
        run_view_type=1,
        max_results=2,
        order_by=["metrics.acc DESC"],
    )
    assert [r.info.run_id for r in first] == [by_acc[0.9], by_acc[0.7]]
    assert first.token is not None
    second = store.search_runs(
        experiment_ids=[exp_id],
        filter_string="",
        run_view_type=1,
        max_results=2,
        order_by=["metrics.acc DESC"],
        page_token=first.token,
    )
    assert [r.info.run_id for r in second] == [by_acc[0.5]]


@pytest.mark.parametrize("prefix,value", [("mlflow.", "value"), ("", "true"), ("", "")])
def test_concurrent_tags_are_retained(
    store: LumlTrackingStore, prefix: str, value: str
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    run_id = _start_run(store)
    tags = [RunTag(f"{prefix}tag{i}", value) for i in range(120)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda tag: store.set_tag(run_id, tag), tags))
    actual = store.get_run(run_id).data.tags
    assert all(actual[tag.key] == value for tag in tags)


@pytest.mark.parametrize("values", [("true", "alice", ""), ("alice", "true", "bob")])
def test_tag_value_transitions_and_delete(
    store: LumlTrackingStore, values: tuple[str, ...]
) -> None:
    run_id = _start_run(store)
    store.log_param(run_id, Param("owner", "original"))
    for value in values:
        store.set_tag(run_id, RunTag("owner", value))
        assert store.get_run(run_id).data.tags["owner"] == value
        assert store.get_run(run_id).data.params["owner"] == "original"
    store.delete_tag(run_id, "owner")
    store.delete_tag(run_id, "owner")
    assert "owner" not in store.get_run(run_id).data.tags
    assert store.get_run(run_id).data.params["owner"] == "original"


def test_concurrent_metadata_namespaces_are_retained(store: LumlTrackingStore) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from luml_mlflow.meta import (
        META_LUML_INTERNAL,
        META_RUN_INFO,
        write_luml_internal,
        write_run_info_field,
    )

    run_id = _start_run(store)

    def write(index: int) -> None:
        store.set_tag(run_id, RunTag(f"mlflow.tag{index}", str(index)))
        store.set_tag(run_id, RunTag(f"flag{index}", "true"))
        write_run_info_field(store._tracker, run_id, f"field{index}", index)
        write_luml_internal(store._tracker, run_id, {f"luml.key{index}": index})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(40)))
    meta = store._tracker.get_experiment_metadata(run_id)
    tags = store.get_run(run_id).data.tags
    for index in range(40):
        assert tags[f"mlflow.tag{index}"] == str(index)
        assert tags[f"flag{index}"] == "true"
        assert meta[META_RUN_INFO][f"field{index}"] == index
        assert meta[META_LUML_INTERNAL][f"luml.key{index}"] == index


def test_concurrent_process_tags_are_retained(store: LumlTrackingStore) -> None:
    import subprocess
    import sys

    run_id = _start_run(store)
    script = """
import sys
from luml_mlflow.store import LumlTrackingStore
from mlflow.entities import RunTag
store = LumlTrackingStore('luml://org1/orbit1')
for i in range(30):
    store.set_tag(sys.argv[1], RunTag(f'mlflow.{sys.argv[2]}.{i}', str(i)))
    store.set_tag(sys.argv[1], RunTag(f'flag.{sys.argv[2]}.{i}', 'true'))
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, run_id, str(worker)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for worker in range(4)
    ]
    for process in processes:
        _, stderr = process.communicate(timeout=60)
        assert process.returncode == 0, stderr
    tags = store.get_run(run_id).data.tags
    for worker in range(4):
        for index in range(30):
            assert tags[f"mlflow.{worker}.{index}"] == str(index)
            assert tags[f"flag.{worker}.{index}"] == "true"


def test_metadata_mutation_failure_rolls_back(store: LumlTrackingStore) -> None:
    from typing import Any

    from luml_mlflow._tracker import mutate_experiment

    run_id = _start_run(store)
    before = store._tracker.get_experiment_metadata(run_id)

    def fail(metadata: dict[str, Any], flags: list[str]) -> None:
        metadata["partial"] = True
        flags.append("partial")
        raise RuntimeError("failed mutation")

    with pytest.raises(RuntimeError, match="failed mutation"):
        mutate_experiment(store._tracker, run_id, fail)
    assert store._tracker.get_experiment_metadata(run_id) == before
    assert "partial" not in store.get_run(run_id).data.tags
