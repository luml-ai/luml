from fastapi import APIRouter, Query, status

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.schemas.experiments import (
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    PaginatedTraces,
    UpdateExperiment,
)

experiments_router = APIRouter(
    prefix="/experiments",
    tags=["experiments"],
)

experiments_handler = ExperimentsHandler()


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
    "/{experiment_id}/metrics/{key}", response_model=ExperimentMetricHistory
)
def get_experiment_metric_history(
    experiment_id: str, key: str
) -> ExperimentMetricHistory:
    return experiments_handler.get_experiment_metric_history(experiment_id, key)


@experiments_router.get("/{experiment_id}/traces", response_model=PaginatedTraces)
def get_experiment_traces(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> PaginatedTraces:
    return experiments_handler.get_experiment_traces(
        experiment_id, limit=limit, cursor=cursor
    )
