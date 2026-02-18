from luml.experiments.backends.sqlite import SQLiteBackend

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.experiments import Experiment, UpdateExperiment
from lumlflow.settings import config


class ExperimentsHandler:
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        self._db_path = db_path
        self.db = SQLiteBackend(self._db_path)

    def delete_experiment(self, experiment_id: str) -> None:
        if not self.db.get_experiment(experiment_id):
            raise NotFound("Experiment not found")
        models = self.db.list_experiment_models(experiment_id)
        if models and len(models) > 0:
            raise ApplicationError(
                "Cannot delete an experiment that has linked models", status_code=409
            )
        try:
            self.db.delete_experiment(experiment_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

    def update_experiment(
        self, experiment_id: str, body: UpdateExperiment
    ) -> Experiment:
        try:
            experiment = self.db.update_experiment(
                experiment_id,
                name=body.name,
                description=body.description,
                tags=body.tags,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if not experiment:
            raise NotFound("Experiment not found")

        return Experiment.model_validate(experiment)
