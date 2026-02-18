from fastapi import APIRouter, status

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.schemas.experiments import Experiment, UpdateExperiment

experiments_router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
)

experiments_handler = ExperimentsHandler()


@experiments_router.patch("/{experiment_id}", response_model=Experiment)
def update_experiment(experiment_id: str, body: UpdateExperiment) -> Experiment:
    return experiments_handler.update_experiment(experiment_id, body)


@experiments_router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment(experiment_id: str) -> None:
    experiments_handler.delete_experiment(experiment_id)
