from fastapi import APIRouter, Query

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    PaginatedTraces,
    Trace,
    TraceDetails,
    TracesSortBy,
    TraceState,
)

experiments_traces_router = APIRouter(
    prefix="/api/experiments/{experiment_id}/traces",
    tags=["experiment-traces"],
)

experiments_handler = ExperimentsHandler()


@experiments_traces_router.get("/all", response_model=list[Trace])
def get_experiment_traces_all(
    experiment_id: str,
    sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
    states: list[TraceState] | None = None,
) -> list[Trace]:
    """
    search: An optional search by trace_id

    states: An optional list of TraceState objects to filter traces by their state.
    """
    return experiments_handler.get_experiment_traces_all(
        experiment_id,
        sort_by=sort_by,
        order=order,
        search=search,
        states=states,
    )


@experiments_traces_router.get("", response_model=PaginatedTraces)
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


@experiments_traces_router.get("/{trace_id}", response_model=TraceDetails)
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails:
    return experiments_handler.get_trace(experiment_id, trace_id)
