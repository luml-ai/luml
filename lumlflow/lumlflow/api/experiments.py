from fastapi import APIRouter, status

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.handlers.models import ModelsHandler
from lumlflow.schemas.experiments import (
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    UpdateExperiment,
)
from lumlflow.schemas.models import Model

experiments_router = APIRouter(
    prefix="/api/experiments",
    tags=["experiments"],
)

experiments_handler = ExperimentsHandler()
models_handler = ModelsHandler()


@experiments_router.get("/{experiment_id}", response_model=ExperimentDetails)
def get_experiment(experiment_id: str) -> ExperimentDetails:
    return experiments_handler.get_experiment(experiment_id)


@experiments_router.patch("/{experiment_id}", response_model=Experiment)
def update_experiment(experiment_id: str, body: UpdateExperiment) -> Experiment:
    return experiments_handler.update_experiment(experiment_id, body)


@experiments_router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: str) -> None:
    experiments_handler.delete_experiment(experiment_id)


@experiments_router.get(
    "/{experiment_id}/metrics/{key:path}", response_model=ExperimentMetricHistory
)
def get_experiment_metric_history(
    experiment_id: str, key: str, max_points: int = 1000
) -> ExperimentMetricHistory:
    return experiments_handler.get_experiment_metric_history(
        experiment_id, key, max_points
    )


@experiments_router.get("/{experiment_id}/models", response_model=list[Model])
def list_experiment_models(experiment_id: str) -> list[Model]:
    return models_handler.list_experiment_models(experiment_id)
