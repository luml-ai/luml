import sqlite3
import tarfile
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from luml.artifacts.model import ModelReference
from luml.experiments.backends._data_types import Model
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def tracker_with_experiment(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="test_exp")
    return tracker, exp_id


@pytest.fixture
def dummy_model_file(tmp_path: Path) -> Path:
    model_path = tmp_path / "dummy_model.luml"
    with tarfile.open(model_path, "w") as tar:
        import io

        data = b"fake model data"
        info = tarfile.TarInfo(name="model.bin")
        info.size = len(data)
        tar.addfile(info, fileobj=io.BytesIO(data))
    return model_path


def test_log_model_with_reference(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    result = tracker.log_model(model_ref, experiment_id=exp_id)

    assert isinstance(result, ModelReference)
    assert Path(result.path).exists()
    assert "/models/" in str(result.path)


def test_log_model_file_copied_to_exp_dir(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
    tmp_path: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    result = tracker.log_model(model_ref, experiment_id=exp_id)

    exp_models_dir = tmp_path / "experiments" / exp_id / "models"
    assert exp_models_dir.exists()
    assert Path(result.path).parent == exp_models_dir


def test_log_model_stored_in_meta_db(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
    tmp_path: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    tracker.log_model(model_ref, name="my_model", tags=["v1"], experiment_id=exp_id)

    meta_db = tmp_path / "experiments" / "meta.db"
    conn = sqlite3.connect(meta_db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, tags, experiment_id FROM models WHERE experiment_id = ?",
        (exp_id,),
    )
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[1] == "my_model"
    assert row[3] == exp_id


def test_log_model_requires_experiment(
    tracker: ExperimentTracker, dummy_model_file: Path
) -> None:
    model_ref = ModelReference(str(dummy_model_file))
    with pytest.raises(ValueError, match="No active experiment"):
        tracker.log_model(model_ref)


def test_log_model_unknown_model_type(
    tracker_with_experiment: tuple[ExperimentTracker, str],
) -> None:
    tracker, exp_id = tracker_with_experiment

    with pytest.raises(ValueError, match="Cannot auto-detect flavor"):
        tracker.log_model("not_a_model", experiment_id=exp_id)


def test_log_model_unknown_flavor(
    tracker_with_experiment: tuple[ExperimentTracker, str],
) -> None:
    tracker, exp_id = tracker_with_experiment

    with pytest.raises(ValueError, match="Unknown flavor"):
        tracker.log_model("not_a_model", flavor="nonexistent", experiment_id=exp_id)


def test_log_model_with_name_and_tags(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    tracker.log_model(
        model_ref, name="prod_model", tags=["production", "v2"],
        experiment_id=exp_id,
    )

    models = tracker.get_models(experiment_id=exp_id)
    assert len(models) == 1
    assert models[0].name == "prod_model"
    assert models[0].tags == ["production", "v2"]


def test_log_model_implicit_experiment_id(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    result = tracker.log_model(model_ref)

    assert isinstance(result, ModelReference)
    assert Path(result.path).exists()


def test_get_models(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    tracker.log_model(model_ref, name="model_a", experiment_id=exp_id)
    tracker.log_model(model_ref, name="model_b", experiment_id=exp_id)

    models = tracker.get_models(experiment_id=exp_id)
    assert len(models) == 2
    names = {m.name for m in models}
    assert names == {"model_a", "model_b"}
    for m in models:
        assert isinstance(m, Model)
        assert m.experiment_id == exp_id


def test_get_model_by_id(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    dummy_model_file: Path,
) -> None:
    tracker, exp_id = tracker_with_experiment
    model_ref = ModelReference(str(dummy_model_file))

    tracker.log_model(model_ref, name="target_model", experiment_id=exp_id)

    models = tracker.get_models(experiment_id=exp_id)
    model_id = models[0].id

    model = tracker.get_model(model_id)
    assert model.name == "target_model"
    assert model.id == model_id


def test_get_model_not_found(tracker: ExperimentTracker) -> None:
    with pytest.raises(ValueError, match="not found"):
        tracker.get_model("nonexistent-id")


def _make_fake_instance(module: str) -> object:
    cls = type("FakeModel", (), {"__module__": module})
    return cls()


def test_detect_flavor_sklearn() -> None:
    obj = _make_fake_instance("sklearn.ensemble._forest")
    assert ExperimentTracker._detect_flavor(obj) == "sklearn"


def test_detect_flavor_xgboost() -> None:
    obj = _make_fake_instance("xgboost.sklearn")
    assert ExperimentTracker._detect_flavor(obj) == "xgboost"


def test_detect_flavor_lightgbm() -> None:
    obj = _make_fake_instance("lightgbm.sklearn")
    assert ExperimentTracker._detect_flavor(obj) == "lightgbm"


def test_detect_flavor_catboost() -> None:
    obj = _make_fake_instance("catboost.core")
    assert ExperimentTracker._detect_flavor(obj) == "catboost"


def test_detect_flavor_langgraph() -> None:
    obj = _make_fake_instance("langgraph.graph.state")
    assert ExperimentTracker._detect_flavor(obj) == "langgraph"


def test_detect_flavor_unknown() -> None:
    obj = _make_fake_instance("some_random_lib")
    with pytest.raises(ValueError, match="Cannot auto-detect flavor"):
        ExperimentTracker._detect_flavor(obj)


def test_log_model_auto_detect_sklearn(
    tracker_with_experiment: tuple[ExperimentTracker, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker, exp_id = tracker_with_experiment

    dummy_model_path = tmp_path / "auto_sklearn.luml"
    with tarfile.open(dummy_model_path, "w") as tar:
        import io

        data = b"sklearn model"
        info = tarfile.TarInfo(name="model.pkl")
        info.size = len(data)
        tar.addfile(info, fileobj=io.BytesIO(data))

    fake_ref = ModelReference(str(dummy_model_path))

    mock_save = MagicMock(return_value=fake_ref)
    fake_module = ModuleType("luml.integrations.sklearn.packaging")
    fake_module.save_sklearn = mock_save  # type: ignore[attr-defined]

    monkeypatch.setitem(
        __import__("sys").modules,
        "luml.integrations.sklearn.packaging",
        fake_module,
    )

    mock_model = _make_fake_instance("sklearn.ensemble._forest")

    import numpy as np

    inputs = np.array([[1, 2], [3, 4]])

    result = tracker.log_model(mock_model, inputs=inputs, experiment_id=exp_id)

    mock_save.assert_called_once()
    assert isinstance(result, ModelReference)
    assert Path(result.path).exists()
