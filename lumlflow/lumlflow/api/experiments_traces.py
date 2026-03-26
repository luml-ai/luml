from typing import Annotated

from fastapi import APIRouter, Body, Query

from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    PaginatedTraces,
    SearchValidationResult,
    Trace,
    TraceColumns,
    TraceDetails,
    TracesSortBy,
    TraceState,
    TraceTypedColumns,
)

experiments_traces_router = APIRouter(
    prefix="/api/experiments/{experiment_id}/traces",
    tags=["experiment-traces"],
)

experiments_general_traces_router = APIRouter(
    prefix="/api/experiments/traces",
    tags=["experiment-traces"],
)

experiments_handler = ExperimentsHandler()


@experiments_traces_router.get("/columns", response_model=TraceColumns)
def get_experiment_trace_columns(experiment_id: str) -> TraceColumns:
    return experiments_handler.get_experiment_trace_columns(experiment_id)


@experiments_traces_router.get("/typed-columns", response_model=TraceTypedColumns)
def get_experiment_trace_typed_columns(experiment_id: str) -> TraceTypedColumns:
    return experiments_handler.get_experiment_trace_typed_columns(experiment_id)


@experiments_traces_router.get("/all", response_model=list[Trace])
def get_experiment_traces_all(
    experiment_id: str,
    sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
    filters: list[str] = Query(default_factory=list),  # noqa: B008
    states: list[TraceState] | None = None,
) -> list[Trace]:
    """
    search: An optional search by trace_id
    filters: list of filter conditions on span attributes, all AND-ed together.
    Each condition: attributes.<key> <op> <value>

    states: An optional list of TraceState objects to filter traces by their state.
    """
    return experiments_handler.get_experiment_traces_all(
        experiment_id,
        sort_by=sort_by,
        order=order,
        search=search,
        filters=filters or None,
        states=states,
    )


@experiments_traces_router.get("", response_model=PaginatedTraces)
def get_experiment_traces(
    experiment_id: str,
    limit: int = Query(default=20, ge=1, le=100),  # noqa: B008
    cursor: str | None = None,
    sort_by: TracesSortBy = TracesSortBy.EXECUTION_TIME,
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
    filters: list[str] = Query(default_factory=list),  # noqa: B008
    states: list[TraceState] | None = None,
) -> PaginatedTraces:
    """
    search: An optional search by trace_id
    filters: list of filter conditions on span attributes, all AND-ed together.
    Each condition: attributes.<key> <op> <value>

    states: An optional list of TraceState objects to filter traces by their state.
    """
    return experiments_handler.get_experiment_traces(
        experiment_id,
        limit=limit,
        cursor=cursor,
        sort_by=sort_by,
        order=order,
        search=search,
        filters=filters or None,
        states=states,
    )


@experiments_general_traces_router.post(
    "/validate-filter", response_model=list[SearchValidationResult]
)
def validate_traces_filter(
    filter_strings: Annotated[list[str], Body(...)],
) -> list[SearchValidationResult]:
    """
    Validate a traces filter string without executing it.

    Supported syntax:
    - **Span attributes**: attributes.<key>
      — string or numeric operators based on value type
      — Operators: =, !=, >, >=, <, <=, LIKE, ILIKE, CONTAINS, IN, NOT IN

    Examples:
     - attributes.http.method = "GET"
     - attributes.http.status_code >= 400
     - attributes.db.statement CONTAINS "SELECT"
     - attributes.http.status_code >= 400 AND attributes.http.status_code < 500
    """
    return experiments_handler.validate_traces_filter(filter_strings)


@experiments_traces_router.get("/{trace_id}", response_model=TraceDetails)
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails:
    return experiments_handler.get_trace(experiment_id, trace_id)
