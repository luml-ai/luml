from fastapi import APIRouter, Query, status
from luml.experiments.backends.data_types import TraceState

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.handlers.models import ModelsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    EvalColumns,
    Experiment,
    ExperimentDetails,
    ExperimentMetricHistory,
    PaginatedEvals,
    PaginatedTraces,
    TraceDetails,
    TracesSortBy,
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
    "/{experiment_id}/metrics/{key}", response_model=ExperimentMetricHistory
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


@experiments_router.get(
    "/{experiment_id}/traces/{trace_id}", response_model=TraceDetails
)
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails:
    return experiments_handler.get_trace(experiment_id, trace_id)


@experiments_router.get("/{experiment_id}/evals/columns", response_model=EvalColumns)
def get_experiment_eval_scores(experiment_id: str) -> EvalColumns:
    return experiments_handler.get_experiment_eval_columns(experiment_id)


@experiments_router.get("/{experiment_id}/evals", response_model=PaginatedEvals)
def get_experiment_evals(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    dataset_id: str | None = None,
    search: str | None = None,
) -> PaginatedEvals:
    """
    search: optional substring filter on eval id

    sort_by: standard column (created_at, updated_at, dataset_id) or
    a score / inputs / outputs / refs key
    """
    return experiments_handler.get_experiment_evals(
        experiment_id,
        limit=limit,
        cursor=cursor,
        sort_by=sort_by,
        order=order,
        dataset_id=dataset_id,
        search=search,
    )


@experiments_router.get("/{experiment_id}/traces", response_model=PaginatedTraces)
def get_experiment_traces(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
    states: list[TraceState] | None = None,
) -> PaginatedTraces:
    """
    search: An optional search by trace_id

    states: An optional list of TraceState objects to filter traces by their state.
    """
    return experiments_handler.get_experiment_traces(
        experiment_id,
        limit=limit,
        cursor=cursor,
        sort_by=sort_by,
        order=order,
        search=search,
        states=states,
    )
