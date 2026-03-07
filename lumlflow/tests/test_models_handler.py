from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.handlers.models import ModelsHandler
from lumlflow.infra.exceptions import NotFound
from lumlflow.schemas.models import UpdateModel


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def handler(tracker: ExperimentTracker) -> ModelsHandler:
    return ModelsHandler(tracker=tracker)


@pytest.fixture
def seeded(
    tmp_path: Path, tracker: ExperimentTracker, handler: ModelsHandler
) -> tuple[ModelsHandler, str, str]:
    exp_id = tracker.start_experiment(name="test-exp")
    model_file = tmp_path / "model.bin"
    model_file.write_bytes(b"fake-model-data")
    model, _ = tracker.backend.log_model(
        exp_id, str(model_file), name="m1", tags=["v1"]
    )
    return handler, exp_id, model.id


class TestListModels:
    def test_empty(self, tracker: ExperimentTracker, handler: ModelsHandler) -> None:
        exp_id = tracker.start_experiment(name="empty")
        result = handler.list_experiment_models(exp_id)
        assert result == []

    def test_with_data(
        self, seeded: tuple[ModelsHandler, str, str]
    ) -> None:
        handler, exp_id, _ = seeded
        result = handler.list_experiment_models(exp_id)
        assert len(result) == 1
        assert result[0].name == "m1"


class TestUpdateModel:
    def test_update_name(
        self, seeded: tuple[ModelsHandler, str, str]
    ) -> None:
        handler, _, model_id = seeded
        updated = handler.update_model(model_id, UpdateModel(name="new-name"))
        assert updated.name == "new-name"

    def test_update_tags(
        self, seeded: tuple[ModelsHandler, str, str]
    ) -> None:
        handler, _, model_id = seeded
        updated = handler.update_model(model_id, UpdateModel(tags=["a", "b"]))
        assert updated.tags == ["a", "b"]

    def test_not_found(self, handler: ModelsHandler) -> None:
        with pytest.raises(NotFound):
            handler.update_model("nonexistent", UpdateModel(name="x"))


class TestDeleteModel:
    def test_delete(
        self, seeded: tuple[ModelsHandler, str, str]
    ) -> None:
        handler, exp_id, model_id = seeded
        handler.delete_model(model_id)
        assert handler.list_experiment_models(exp_id) == []

    def test_not_found(self, handler: ModelsHandler) -> None:
        with pytest.raises(NotFound):
            handler.delete_model("nonexistent")
