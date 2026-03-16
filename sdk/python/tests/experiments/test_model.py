import io
import json
import sqlite3
import tarfile
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import numpy as np
import pytest

from luml.artifacts.model import ModelReference
from luml.experiments.backends.data_types import (
    Model,
)
from luml.experiments.tracker import ExperimentTracker
from tests.experiments.conftest import _meta_db


def _mock_flavor(
    monkeypatch: pytest.MonkeyPatch,
    flavor: str,
    module_path: str,
    func_name: str,
    fake_ref: ModelReference,
) -> MagicMock:
    mock_save = MagicMock(return_value=fake_ref)
    fake_module = ModuleType(module_path)
    setattr(fake_module, func_name, mock_save)
    monkeypatch.setitem(
        __import__("sys").modules,
        module_path,
        fake_module,
    )
    return mock_save


def _make_fake_instance(module: str) -> object:
    cls = type("FakeModel", (), {"__module__": module})
    return cls()


# (flavor, module_path, func_name, model_module_prefix)
_FLAVOR_PARAMS = [
    (
        "sklearn",
        "luml.integrations.sklearn.packaging",
        "save_sklearn",
        "sklearn.ensemble._forest",
    ),
    (
        "xgboost",
        "luml.integrations.xgboost.packaging",
        "save_xgboost",
        "xgboost.sklearn",
    ),
    (
        "lightgbm",
        "luml.integrations.lightgbm.packaging",
        "save_lightgbm",
        "lightgbm.sklearn",
    ),
    (
        "catboost",
        "luml.integrations.catboost.packaging",
        "save_catboost",
        "catboost.core",
    ),
    (
        "langgraph",
        "luml.integrations.langgraph.packaging",
        "save_langgraph",
        "langgraph.graph.state",
    ),
]

_FLAVORS_WITH_INPUTS = {"sklearn", "xgboost", "lightgbm"}
_FLAVORS_WITHOUT_INPUTS = {"catboost", "langgraph"}


class TestLogModel:
    def test_log_model_with_reference(
        self,
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
        self,
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
        self,
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
        self, tracker: ExperimentTracker, dummy_model_file: Path
    ) -> None:
        model_ref = ModelReference(str(dummy_model_file))
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_model(model_ref)

    def test_log_model_unknown_model_type(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        with pytest.raises(ValueError, match="Cannot auto-detect flavor"):
            tracker.log_model("not_a_model", experiment_id=exp_id)

    def test_log_model_unknown_flavor(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        with pytest.raises(ValueError, match="Unknown flavor"):
            tracker.log_model("not_a_model", flavor="nonexistent", experiment_id=exp_id)

    def test_log_model_with_name_and_tags(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        model_ref = ModelReference(str(dummy_model_file))

        tracker.log_model(
            model_ref,
            name="prod_model",
            tags=["production", "v2"],
            experiment_id=exp_id,
        )

        models = tracker.get_models(experiment_id=exp_id)
        assert len(models) == 1
        assert models[0].name == "prod_model"
        assert models[0].tags == ["production", "v2"]

    def test_log_model_implicit_experiment_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        model_ref = ModelReference(str(dummy_model_file))

        result = tracker.log_model(model_ref)

        assert isinstance(result, ModelReference)
        assert Path(result.path).exists()

    @pytest.mark.parametrize(
        ("flavor", "module_path", "func_name", "model_module"),
        _FLAVOR_PARAMS,
        ids=[p[0] for p in _FLAVOR_PARAMS],
    )
    def test_log_model_auto_detect_persists_to_db_and_disk(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        flavor: str,
        module_path: str,
        func_name: str,
        model_module: str,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_save = _mock_flavor(monkeypatch, flavor, module_path, func_name, fake_ref)
        mock_model = _make_fake_instance(model_module)

        result = tracker.log_model(
            mock_model,
            name=f"{flavor}_model",
            tags=[flavor, "test"],
            experiment_id=exp_id,
        )

        mock_save.assert_called_once()
        assert isinstance(result, ModelReference)
        assert Path(result.path).exists()

        models_dir = tmp_path / "experiments" / exp_id / "models"
        assert models_dir.exists()
        assert Path(result.path).parent == models_dir

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT name, tags, experiment_id FROM models WHERE experiment_id = ?",
            (exp_id,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == f"{flavor}_model"
        assert json.loads(row[1]) == [flavor, "test"]
        assert row[2] == exp_id

    @pytest.mark.parametrize(
        ("flavor", "module_path", "func_name", "model_module"),
        [p for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITH_INPUTS],
        ids=[p[0] for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITH_INPUTS],
    )
    def test_inputs_forwarded_when_provided(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        flavor: str,
        module_path: str,
        func_name: str,
        model_module: str,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_save = _mock_flavor(monkeypatch, flavor, module_path, func_name, fake_ref)
        mock_model = _make_fake_instance(model_module)
        sample_inputs = [[1, 2], [3, 4]]

        tracker.log_model(mock_model, inputs=sample_inputs, experiment_id=exp_id)

        args, _ = mock_save.call_args
        assert args[0] is mock_model
        assert args[1] is sample_inputs

    @pytest.mark.parametrize(
        ("flavor", "module_path", "func_name", "model_module"),
        [p for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITHOUT_INPUTS],
        ids=[p[0] for p in _FLAVOR_PARAMS if p[0] in _FLAVORS_WITHOUT_INPUTS],
    )
    def test_inputs_not_forwarded_when_none(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        flavor: str,
        module_path: str,
        func_name: str,
        model_module: str,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_save = _mock_flavor(monkeypatch, flavor, module_path, func_name, fake_ref)
        mock_model = _make_fake_instance(model_module)

        tracker.log_model(mock_model, experiment_id=exp_id)

        args, _ = mock_save.call_args
        assert len(args) == 1
        assert args[0] is mock_model

    def test_log_model_with_reference_skips_save(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        model_ref = ModelReference(str(dummy_model_file))

        result = tracker.log_model(
            model_ref, name="ref_model", tags=["v1"], experiment_id=exp_id
        )

        assert isinstance(result, ModelReference)
        assert Path(result.path).exists()
        assert Path(result.path).parent == tmp_path / "experiments" / exp_id / "models"

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT name, tags FROM models WHERE experiment_id = ?", (exp_id,)
        ).fetchone()
        conn.close()

        assert row[0] == "ref_model"
        assert json.loads(row[1]) == ["v1"]

    def test_log_model_cleans_up_temp_file(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        _mock_flavor(
            monkeypatch,
            "sklearn",
            "luml.integrations.sklearn.packaging",
            "save_sklearn",
            fake_ref,
        )
        mock_model = _make_fake_instance("sklearn.ensemble._forest")

        result = tracker.log_model(mock_model, inputs=[[1]], experiment_id=exp_id)

        assert not dummy_model_file.exists(), "Temp model file should be cleaned up"
        assert Path(result.path).exists(), "Stored copy should still exist"

    def test_get_models_returns_all_logged(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ref = ModelReference(str(dummy_model_file))

        tracker.log_model(ref, name="model_a")
        tracker.log_model(ref, name="model_b", tags=["prod"])

        models = tracker.get_models()
        assert len(models) == 2
        names = {m.name for m in models}
        assert names == {"model_a", "model_b"}
        for m in models:
            assert isinstance(m, Model)
            assert m.experiment_id == exp_id

    def test_get_model_by_id_returns_correct_record(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ref = ModelReference(str(dummy_model_file))

        tracker.log_model(ref, name="target", tags=["v2"])

        models = tracker.get_models()
        model_id = models[0].id

        model = tracker.get_model(model_id)
        assert model.name == "target"
        assert model.tags == ["v2"]
        assert model.experiment_id == exp_id
        assert model.path is not None

        conn = _meta_db(tmp_path)
        row = conn.execute(
            "SELECT id, name FROM models WHERE id = ?", (model_id,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "target"

    def test_log_model_explicit_flavor_overrides_auto_detect(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        fake_ref = ModelReference(str(dummy_model_file))
        mock_xgb = _mock_flavor(
            monkeypatch,
            "xgboost",
            "luml.integrations.xgboost.packaging",
            "save_xgboost",
            fake_ref,
        )
        mock_model = _make_fake_instance("sklearn.ensemble._forest")

        tracker.log_model(
            mock_model, flavor="xgboost", inputs=[[1]], experiment_id=exp_id
        )

        mock_xgb.assert_called_once()
        args, _ = mock_xgb.call_args
        assert args[0] is mock_model

    def test_log_model_auto_detect_sklearn(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        dummy_model_path = tmp_path / "auto_sklearn.luml"
        with tarfile.open(dummy_model_path, "w") as tar:
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

        inputs = np.array([[1, 2], [3, 4]])

        result = tracker.log_model(mock_model, inputs=inputs, experiment_id=exp_id)

        mock_save.assert_called_once()
        assert isinstance(result, ModelReference)
        assert Path(result.path).exists()


class TestListExperimentModels:
    def test_returns_empty_list_when_no_models_logged(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        models = tracker.list_experiment_models(exp_id)

        assert models == []

    def test_returns_correct_model_fields(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="my_model",
            tags=["v1", "prod"],
            experiment_id=exp_id,
        )

        models = tracker.list_experiment_models(exp_id)

        assert len(models) == 1
        m = models[0]
        assert isinstance(m, Model)
        assert m.name == "my_model"
        assert m.tags == ["v1", "prod"]
        assert m.experiment_id == exp_id
        assert m.id is not None
        assert m.created_at is not None

    def test_returns_all_models_for_experiment(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ref = ModelReference(str(dummy_model_file))
        tracker.log_model(ref, name="model_a", experiment_id=exp_id)
        tracker.log_model(ref, name="model_b", experiment_id=exp_id)
        tracker.log_model(ref, name="model_c", experiment_id=exp_id)

        models = tracker.list_experiment_models(exp_id)

        assert len(models) == 3
        assert {m.name for m in models} == {"model_a", "model_b", "model_c"}

    def test_models_are_isolated_per_experiment(
        self,
        tracker: ExperimentTracker,
        dummy_model_file: Path,
    ) -> None:
        id1 = tracker.start_experiment(name="exp1")
        id2 = tracker.start_experiment(name="exp2")
        ref = ModelReference(str(dummy_model_file))
        tracker.log_model(ref, name="model_for_1", experiment_id=id1)
        tracker.log_model(ref, name="model_for_2", experiment_id=id2)

        models1 = tracker.list_experiment_models(id1)
        models2 = tracker.list_experiment_models(id2)

        assert len(models1) == 1
        assert models1[0].name == "model_for_1"
        assert len(models2) == 1
        assert models2[0].name == "model_for_2"

    def test_model_without_tags_has_empty_tags_list(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="untagged",
            experiment_id=exp_id,
        )

        models = tracker.list_experiment_models(exp_id)

        assert models[0].tags == []


class TestDeleteModel:
    def test_removes_model_from_db(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="to_delete",
            experiment_id=exp_id,
        )
        model_id = tracker.list_experiment_models(exp_id)[0].id

        tracker.delete_model(model_id)

        assert tracker.list_experiment_models(exp_id) == []

    def test_deletes_model_file_from_disk(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="to_delete",
            experiment_id=exp_id,
        )
        model = tracker.list_experiment_models(exp_id)[0]
        model_file = tmp_path / "experiments" / model.path
        assert model_file.exists()

        tracker.delete_model(model.id)

        assert not model_file.exists()

    def test_does_not_raise_for_nonexistent_model_id(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.delete_model("nonexistent-id")

    def test_skips_file_deletion_when_path_is_none(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        tmp_path: Path,
    ) -> None:
        import uuid

        tracker, exp_id = tracker_with_experiment
        model_id = uuid.uuid4().hex
        conn = _meta_db(tmp_path)
        conn.execute(
            "INSERT INTO models (id, name, tags, path, size, experiment_id) VALUES (?, ?, ?, ?, ?, ?)",
            (model_id, "no-file-model", "[]", None, None, exp_id),
        )
        conn.commit()
        conn.close()

        tracker.delete_model(model_id)

        assert tracker.list_experiment_models(exp_id) == []

    def test_skips_unlink_when_file_already_missing(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
        tmp_path: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(ModelReference(str(dummy_model_file)), experiment_id=exp_id)
        model = tracker.list_experiment_models(exp_id)[0]
        (tmp_path / "experiments" / model.path).unlink()

        tracker.delete_model(model.id)

        assert tracker.list_experiment_models(exp_id) == []


class TestUpdateModel:
    def test_updates_name(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)), name="old_name", experiment_id=exp_id
        )
        model_id = tracker.list_experiment_models(exp_id)[0].id

        result = tracker.update_model(model_id, name="new_name")

        assert result is not None
        assert result.name == "new_name"

    def test_updates_tags(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="m",
            tags=["v1"],
            experiment_id=exp_id,
        )
        model_id = tracker.list_experiment_models(exp_id)[0].id

        result = tracker.update_model(model_id, tags=["v2", "prod"])

        assert result is not None
        assert result.tags == ["v2", "prod"]

    def test_updates_name_and_tags(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="old",
            tags=["v1"],
            experiment_id=exp_id,
        )
        model_id = tracker.list_experiment_models(exp_id)[0].id

        result = tracker.update_model(model_id, name="new", tags=["v2"])

        assert result is not None
        assert result.name == "new"
        assert result.tags == ["v2"]

    def test_returns_current_model_when_no_fields_provided(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)),
            name="unchanged",
            tags=["x"],
            experiment_id=exp_id,
        )
        model_id = tracker.list_experiment_models(exp_id)[0].id

        result = tracker.update_model(model_id)

        assert result is not None
        assert result.name == "unchanged"
        assert result.tags == ["x"]

    def test_returns_none_for_nonexistent_model(
        self, tracker: ExperimentTracker
    ) -> None:
        result = tracker.update_model("nonexistent-id", name="x")

        assert result is None

    def test_update_persists_in_listing(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        dummy_model_file: Path,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_model(
            ModelReference(str(dummy_model_file)), name="before", experiment_id=exp_id
        )
        model_id = tracker.list_experiment_models(exp_id)[0].id

        tracker.update_model(model_id, name="after", tags=["updated"])

        models = tracker.list_experiment_models(exp_id)
        assert models[0].name == "after"
        assert models[0].tags == ["updated"]


class TestGetModels:
    def test_get_models_requires_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.get_models()

    def test_get_models_empty(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, _ = tracker_with_experiment
        models = tracker.get_models()
        assert models == []

    def test_get_models(
        self,
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


class TestGetModel:
    def test_get_model_by_id(
        self,
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

    def test_get_model_not_found(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="not found"):
            tracker.get_model("nonexistent-id")


class TestDetectFlavor:
    def test_detect_flavor_sklearn(self) -> None:
        obj = _make_fake_instance("sklearn.ensemble._forest")
        assert ExperimentTracker._detect_flavor(obj) == "sklearn"

    def test_detect_flavor_xgboost(self) -> None:
        obj = _make_fake_instance("xgboost.sklearn")
        assert ExperimentTracker._detect_flavor(obj) == "xgboost"

    def test_detect_flavor_lightgbm(self) -> None:
        obj = _make_fake_instance("lightgbm.sklearn")
        assert ExperimentTracker._detect_flavor(obj) == "lightgbm"

    def test_detect_flavor_catboost(self) -> None:
        obj = _make_fake_instance("catboost.core")
        assert ExperimentTracker._detect_flavor(obj) == "catboost"

    def test_detect_flavor_langgraph(self) -> None:
        obj = _make_fake_instance("langgraph.graph.state")
        assert ExperimentTracker._detect_flavor(obj) == "langgraph"

    def test_detect_flavor_unknown(self) -> None:
        obj = _make_fake_instance("some_random_lib")
        with pytest.raises(ValueError, match="Cannot auto-detect flavor"):
            ExperimentTracker._detect_flavor(obj)
