from luml.experiments.tracker import ExperimentTracker

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.models import Model, UpdateModel
from lumlflow.settings import get_tracker


class ModelsHandler:
    def __init__(self, tracker: ExperimentTracker | None = None) -> None:
        self.tracker = tracker or get_tracker()

    def list_experiment_models(self, experiment_id: str) -> list[Model]:
        try:
            models = self.tracker.list_experiment_models(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        return [Model.model_validate(m) for m in models]

    def update_model(self, model_id: str, body: UpdateModel) -> Model:
        try:
            self.tracker.get_model(model_id)
        except ValueError as e:
            raise NotFound("Model not found") from e
        try:
            model = self.tracker.update_model(model_id, name=body.name, tags=body.tags)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        if not model:
            raise NotFound("Model not found")
        return Model.model_validate(model)

    def delete_model(self, model_id: str) -> None:
        try:
            self.tracker.get_model(model_id)
        except ValueError as e:
            raise NotFound("Model not found") from e
        try:
            self.tracker.delete_model(model_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
