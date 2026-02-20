from luml.experiments.backends.sqlite import SQLiteBackend

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.models import Model, UpdateModel
from lumlflow.settings import config


class ModelsHandler:
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        self.db = SQLiteBackend(db_path)

    def list_experiment_models(self, experiment_id: str) -> list[Model]:
        try:
            models = self.db.list_experiment_models(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        return [Model.model_validate(m) for m in models]

    def update_model(self, model_id: str, body: UpdateModel) -> Model:
        if not self.db.get_model(model_id):
            raise NotFound("Model not found")
        try:
            model = self.db.update_model(model_id, name=body.name, tags=body.tags)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
        if not model:
            raise NotFound("Model not found")
        return Model.model_validate(model)

    def delete_model(self, model_id: str) -> None:
        if not self.db.get_model(model_id):
            raise NotFound("Model not found")
        try:
            self.db.delete_model(model_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e
