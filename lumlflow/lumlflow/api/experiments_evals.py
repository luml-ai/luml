from typing import Annotated

from fastapi import APIRouter, Body, Query

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    Eval,
    EvalColumns,
    EvalTypedColumns,
    PaginatedEvals,
    SearchValidationResult,
)

experiments_evals_router = APIRouter(
    prefix="/api/experiments/{experiment_id}/evals",
    tags=["experiment-evals"],
)

experiments_general_evals_router = APIRouter(
    prefix="/api/experiments/evals",
    tags=["experiment-evals"],
)

experiments_handler = ExperimentsHandler()


@experiments_evals_router.get("/columns", response_model=EvalColumns)
def get_experiment_eval_columns(
    experiment_id: str,
    dataset_id: str | None = None,
) -> EvalColumns:
    return experiments_handler.get_experiment_eval_columns(experiment_id, dataset_id)


@experiments_evals_router.get("/typed-columns", response_model=EvalTypedColumns)
def get_experiment_eval_typed_columns(
    experiment_id: str,
    dataset_id: str | None = None,
) -> EvalTypedColumns:
    return experiments_handler.get_experiment_eval_typed_columns(
        experiment_id, dataset_id
    )


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
    filters: list[str] = Query(default_factory=list),  # noqa: B008
) -> list[Eval]:
    """
    search: optional substring filter on eval id

    filters: list of filter conditions, all AND-ed together.
    Each condition: <field> <op> <value>
    Fields: id, dataset_id, created_at, updated_at,
            inputs.<key>, outputs.<key>, refs.<key>, scores.<key>, metadata.<key>

    sort_by: standard column (created_at, updated_at, dataset_id) or
    a score / inputs / outputs / refs key / metadata
    """
    return experiments_handler.get_experiment_evals_all(
        experiment_id,
        sort_by=sort_by,
        order=order,
        dataset_id=dataset_id,
        search=search,
        filters=filters or None,
    )


@experiments_evals_router.get("", response_model=PaginatedEvals)
def get_experiment_evals(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),  # noqa: B008
    cursor: str | None = None,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    dataset_id: str | None = None,
    search: str | None = None,
    filters: list[str] = Query(default_factory=list),  # noqa: B008
) -> PaginatedEvals:
    """
    search: optional substring filter on eval id

    filters: list of filter conditions, all AND-ed together.
    Each condition: <field> <op> <value>
    Fields: id, dataset_id, created_at, updated_at,
            inputs.<key>, outputs.<key>, refs.<key>, scores.<key>, metadata.<key>

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
        filters=filters or None,
    )


@experiments_general_evals_router.post(
    "/validate-filter", response_model=list[SearchValidationResult]
)
def validate_evals_filter(
    filter_strings: Annotated[list[str], Body(...)],
) -> list[SearchValidationResult]:
    """
    Validate an evals filter string without executing it.

    Supported syntax:
    - **Bare attributes**: id, dataset_id — operators:
        =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
    - **Date attributes**: created_at, updated_at — operators: =, !=, >, >=, <, <=
    - **JSON fields**:
        inputs.<key>, outputs.<key>, refs.<key>, scores.<key>, metadata.<key>
      — string or numeric operators based on value type

    Examples:
     - id = "abc123"
     - dataset_id IN ("ds1", "ds2")
     - created_at > "2024-01-01"
     - outputs.prediction LIKE "%bert%"
     - scores.accuracy > 0.9
     - scores.accuracy > 0.8 AND metadata.latency_ms < 500
    """
    return experiments_handler.validate_evals_filter(filter_strings)


@experiments_evals_router.get("/{eval_id}", response_model=Eval)
def get_eval(experiment_id: str, eval_id: str) -> Eval:
    return experiments_handler.get_eval(experiment_id, eval_id)
