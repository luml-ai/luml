"""Tests for the MLflow 3.x LoggedModel store API on the luml store.

MLflow's ``log_model`` drives this API: ``create_logged_model`` (PENDING) →
``log_outputs`` → write artifacts via the repo resolved from the model's
``artifact_location`` → ``finalize_logged_model`` (READY). The integration test
mirrors that sequence against a single store instance.
"""

from pathlib import Path

import pytest
from luml_mlflow.artifact_repo import FNNX_SUFFIX, LumlArtifactRepository
from luml_mlflow.store import LumlTrackingStore
from mlflow.entities import LoggedModelStatus, LoggedModelTag
from mlflow.entities.logged_model_parameter import LoggedModelParameter
from mlflow.exceptions import MlflowException


@pytest.fixture
def store(temp_store: Path) -> LumlTrackingStore:
    return LumlTrackingStore("luml://org1/orbit1")


@pytest.fixture
def run_id(store: LumlTrackingStore) -> tuple[str, str]:
    exp_id = store.create_experiment("training")
    run = store.create_run(exp_id, user_id="alice", start_time=0)
    return exp_id, run.info.run_id


def test_create_logged_model_is_pending_and_routes_to_run(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    lm = store.create_logged_model(
        exp_id,
        name="rf",
        source_run_id=rid,
        tags=[LoggedModelTag("k", "v")],
        params=[LoggedModelParameter("p", "1")],
        model_type="sklearn",
    )

    assert lm.status == LoggedModelStatus.PENDING
    assert lm.name == "rf"
    assert lm.source_run_id == rid
    assert lm.tags == {"k": "v"}
    assert lm.params == {"p": "1"}
    # artifact_location must resolve to the *source run's* luml repo so MLflow's
    # log_model_artifacts routes the model dir through LumlArtifactRepository.
    assert lm.artifact_location == store._artifact_uri_for_run(rid, model_name="rf")
    location = LumlArtifactRepository(lm.artifact_location)._location
    assert location.run_id == rid
    assert location.model_name == "rf"


def test_create_logged_model_unknown_experiment_raises(
    store: LumlTrackingStore,
) -> None:
    with pytest.raises(MlflowException, match="not found"):
        store.create_logged_model("does-not-exist", name="rf")


def test_create_logged_model_name_rides_on_artifact_location(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    from luml_mlflow.uri import parse_artifact_uri

    exp_id, rid = run_id
    named = store.create_logged_model(exp_id, name="rf", source_run_id=rid)
    unnamed = store.create_logged_model(exp_id, source_run_id=rid)

    assert parse_artifact_uri(named.artifact_location).model_name == "rf"
    assert parse_artifact_uri(unnamed.artifact_location).model_name is None


def test_get_logged_model_round_trips(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    created = store.create_logged_model(exp_id, name="rf", source_run_id=rid)

    fetched = store.get_logged_model(created.model_id)

    assert fetched.model_id == created.model_id
    assert fetched.name == "rf"


def test_get_logged_model_missing_raises(store: LumlTrackingStore) -> None:
    with pytest.raises(MlflowException, match="not found"):
        store.get_logged_model("nope")


def test_finalize_logged_model_marks_ready(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    created = store.create_logged_model(exp_id, name="rf", source_run_id=rid)

    finalized = store.finalize_logged_model(created.model_id, LoggedModelStatus.READY)

    assert finalized.status == LoggedModelStatus.READY
    assert store.get_logged_model(created.model_id).status == LoggedModelStatus.READY


def test_set_and_delete_logged_model_tags(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    created = store.create_logged_model(exp_id, name="rf", source_run_id=rid)

    store.set_logged_model_tags(
        created.model_id, [LoggedModelTag("stage", "prod"), LoggedModelTag("x", "1")]
    )
    assert store.get_logged_model(created.model_id).tags == {"stage": "prod", "x": "1"}

    store.delete_logged_model_tag(created.model_id, "x")
    assert store.get_logged_model(created.model_id).tags == {"stage": "prod"}


def test_log_outputs_is_accepted(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    lm = store.create_logged_model(exp_id, name="rf", source_run_id=rid)
    # MLflow records the run -> model linkage; must not raise.
    store.log_outputs(rid, models=[lm])


def test_search_logged_models_scopes_by_experiment(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    created = store.create_logged_model(exp_id, name="rf", source_run_id=rid)

    found = store.search_logged_models([exp_id])
    assert [m.model_id for m in found] == [created.model_id]

    # The run-details page must not 500 for an experiment with no models.
    other = store.create_experiment("other")
    assert list(store.search_logged_models([other])) == []


def test_search_logged_models_respects_max_results(
    store: LumlTrackingStore, run_id: tuple[str, str]
) -> None:
    exp_id, rid = run_id
    store.create_logged_model(exp_id, name="a", source_run_id=rid)
    store.create_logged_model(exp_id, name="b", source_run_id=rid)
    assert len(store.search_logged_models([exp_id], max_results=1)) == 1


def test_logged_model_artifacts_land_as_luml_model(
    store: LumlTrackingStore, run_id: tuple[str, str], tmp_path: Path
) -> None:
    """End-to-end: the model dir written to the LoggedModel's artifact_location
    is converted to fnnx and stored as a luml model under the run."""
    pytest.importorskip("sklearn")
    import mlflow.sklearn
    import pandas as pd
    from mlflow.models.signature import infer_signature
    from sklearn.ensemble import RandomForestClassifier

    exp_id, rid = run_id
    lm = store.create_logged_model(exp_id, name="rf", source_run_id=rid)

    model_dir = tmp_path / "model"
    x = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0, 0.0]})
    y = [0, 1, 0, 1]
    model = RandomForestClassifier(n_estimators=5, random_state=0).fit(x, y)
    mlflow.sklearn.save_model(
        model, str(model_dir), signature=infer_signature(x, model.predict(x))
    )

    # Mirror MLflow's log_model_artifacts: repo resolved from artifact_location.
    LumlArtifactRepository(lm.artifact_location).log_artifacts(str(model_dir))

    models = store._tracker.get_models(experiment_id=rid)
    assert len(models) == 1
    assert (models[0].path or "").endswith(FNNX_SUFFIX)
