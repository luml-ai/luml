from fastapi import APIRouter, Query

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    Eval,
    EvalColumns,
    PaginatedEvals,
)

experiments_evals_router = APIRouter(
    prefix="/api/experiments/{experiment_id}/evals",
    tags=["experiment-evals"],
)

experiments_handler = ExperimentsHandler()


@experiments_evals_router.get("/columns", response_model=EvalColumns)
def get_experiment_eval_columns(
    experiment_id: str,
    dataset_id: str | None = None,
) -> EvalColumns:
    return experiments_handler.get_experiment_eval_columns(experiment_id, dataset_id)


@experiments_evals_router.get("/average-scores", response_model=dict[str, float])
def get_experiment_eval_average_scores(
    experiment_id: str,
    dataset_id: str | None = None,
) -> dict[str, float]:
    return experiments_handler.get_experiment_eval_average_scores(
        experiment_id, dataset_id
    )


@experiments_evals_router.get("/dataset-ids", response_model=list[str])
def get_experiment_eval_dataset_ids(experiment_id: str) -> list[str]:
    return experiments_handler.get_experiment_eval_dataset_ids(experiment_id)


@experiments_evals_router.get("/all", response_model=list[Eval])
def get_experiment_evals_all(
    experiment_id: str,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    dataset_id: str | None = None,
    search: str | None = None,
) -> list[Eval]:
    """
    search: optional substring filter on eval id

    sort_by: standard column (created_at, updated_at, dataset_id) or
    a score / inputs / outputs / refs key / metadata
    """
    return experiments_handler.get_experiment_evals_all(
        experiment_id,
        sort_by=sort_by,
        order=order,
        dataset_id=dataset_id,
        search=search,
    )


@experiments_evals_router.get("", response_model=PaginatedEvals)
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
    a score / inputs / outputs / refs key / metadata
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


@experiments_evals_router.get("/{eval_id}", response_model=Eval)
def get_eval(experiment_id: str, eval_id: str) -> Eval:
    return experiments_handler.get_eval(experiment_id, eval_id)
