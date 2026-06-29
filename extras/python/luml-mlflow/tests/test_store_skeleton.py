from pathlib import Path

import pytest
from luml_mlflow.store import DEFAULT_EXPERIMENT_NAME, LumlTrackingStore


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


def test_default_experiment_is_auto_created(store: LumlTrackingStore) -> None:
    default = store.get_experiment_by_name(DEFAULT_EXPERIMENT_NAME)
    assert default is not None
    assert default.name == DEFAULT_EXPERIMENT_NAME


def test_mlflow_experiment_maps_to_luml_group(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    # MLflow experiment id == luml group id
    group_ids = {g.id for g in store._tracker.list_groups()}
    assert exp_id in group_ids
    # Round trip
    exp = store.get_experiment(exp_id)
    assert exp.name == "fraud"
    assert exp.experiment_id == exp_id


def test_get_experiment_by_name_returns_none_when_missing(
    store: LumlTrackingStore,
) -> None:
    assert store.get_experiment_by_name("nope") is None


def test_duplicate_experiment_name_raises(store: LumlTrackingStore) -> None:
    from mlflow.exceptions import MlflowException

    store.create_experiment("fraud")
    with pytest.raises(MlflowException, match="already exists"):
        store.create_experiment("fraud")


def test_create_run_maps_to_luml_experiment(store: LumlTrackingStore) -> None:
    exp_id = store.create_experiment("fraud")
    run = store.create_run(
        experiment_id=exp_id,
        user_id="alice",
        start_time=0,
        tags=[],
        run_name="r1",
    )
    # MLflow run id == luml experiment id
    luml_experiments = store._tracker.list_experiments()
    assert run.info.run_id in {e.id for e in luml_experiments}
    # Right group
    record = store._tracker.get_experiment_record(run.info.run_id)
    assert record is not None
    assert record.group_name == "fraud"
    assert record.name == "r1"
    # Round trip
    fetched = store.get_run(run.info.run_id)
    assert fetched.info.run_id == run.info.run_id
    assert fetched.info.run_name == "r1"
    assert fetched.info.experiment_id == exp_id


def test_terminology_offset_does_not_swap_ids(store: LumlTrackingStore) -> None:
    """An MLflow ``experiment_id`` is *never* a luml experiment id, and an
    MLflow ``run_id`` is *never* a luml group id."""
    exp_id = store.create_experiment("fraud")
    run = store.create_run(exp_id, user_id="", start_time=0, tags=[], run_name="r")
    luml_group_ids = {g.id for g in store._tracker.list_groups()}
    luml_experiment_ids = {e.id for e in store._tracker.list_experiments()}
    assert exp_id in luml_group_ids
    assert exp_id not in luml_experiment_ids
    assert run.info.run_id in luml_experiment_ids
    assert run.info.run_id not in luml_group_ids


def test_artifact_uri_is_target_aware(temp_store: Path) -> None:
    local = LumlTrackingStore("luml://local")
    remote = LumlTrackingStore("luml://org1/orbit1")
    assert local._artifact_uri_for_run("r1").startswith("luml://local")
    assert remote._artifact_uri_for_run("r1").startswith("luml://org1/orbit1")


def test_unsupported_warn_returns_default(
    store: LumlTrackingStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        store.log_inputs("some-run", datasets=["dataset"])
    assert any("log_inputs" in r.message for r in caplog.records)


def test_unsupported_raise(
    store: LumlTrackingStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from luml_mlflow import config as config_mod

    monkeypatch.setenv("LUML_MLFLOW_ON_UNSUPPORTED", "raise")
    config_mod.reset_settings_cache()
    with pytest.raises(NotImplementedError, match="restore_run"):
        store.restore_run("r1")


def test_search_experiments_returns_groups(store: LumlTrackingStore) -> None:
    store.create_experiment("a")
    store.create_experiment("b")
    page = store.search_experiments()
    names = {e.name for e in page}
    assert {DEFAULT_EXPERIMENT_NAME, "a", "b"}.issubset(names)


def test_set_experiment_tag_round_trips(store: LumlTrackingStore) -> None:
    from mlflow.entities import ExperimentTag

    exp_id = store.create_experiment("fraud")
    store.set_experiment_tag(exp_id, ExperimentTag("team", "ml"))
    store.set_experiment_tag(exp_id, ExperimentTag("priority", "high"))

    assert store.get_experiment(exp_id).tags == {"team": "ml", "priority": "high"}
    # Also reachable by name.
    by_name = store.get_experiment_by_name("fraud")
    assert by_name is not None
    assert by_name.tags == {"team": "ml", "priority": "high"}


def test_set_experiment_tag_overwrites_existing_key(store: LumlTrackingStore) -> None:
    from mlflow.entities import ExperimentTag

    exp_id = store.create_experiment("fraud")
    store.set_experiment_tag(exp_id, ExperimentTag("stage", "dev"))
    store.set_experiment_tag(exp_id, ExperimentTag("stage", "prod"))
    assert store.get_experiment(exp_id).tags == {"stage": "prod"}


def test_experiment_tag_value_with_equals_round_trips(
    store: LumlTrackingStore,
) -> None:
    from mlflow.entities import ExperimentTag

    exp_id = store.create_experiment("fraud")
    store.set_experiment_tag(exp_id, ExperimentTag("query", "a=b=c"))
    assert store.get_experiment(exp_id).tags == {"query": "a=b=c"}


def test_create_experiment_persists_initial_tags(store: LumlTrackingStore) -> None:
    from mlflow.entities import ExperimentTag

    exp_id = store.create_experiment(
        "fraud", tags=[ExperimentTag("owner", "alice"), ExperimentTag("note", "")]
    )
    assert store.get_experiment(exp_id).tags == {"owner": "alice", "note": ""}


def test_set_experiment_tag_missing_experiment_raises(
    store: LumlTrackingStore,
) -> None:
    from mlflow.entities import ExperimentTag
    from mlflow.exceptions import MlflowException

    with pytest.raises(MlflowException, match="not found"):
        store.set_experiment_tag("nonexistent", ExperimentTag("k", "v"))
