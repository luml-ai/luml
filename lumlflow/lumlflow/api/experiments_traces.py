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
    search: An optional search by trace_id.
    filters: List of filter conditions, all AND-ed together. Supported fields:
    - trace_id / id — string ops: =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
    - state — =, !=, IN, NOT IN (values: "ok", "error", "in_progress", "unspecified")
    - execution_time — numeric ops: =, !=, >, >=, <, <= (nanoseconds)
    - span_count — numeric ops: =, !=, >, >=, <, <=
    - created_at — date ops: =, !=, >, >=, <, <= (ISO string)
    - evals — string ops: =, !=, LIKE, ILIKE, CONTAINS (matches eval_id)
    - attributes.<key> — string or numeric ops based on value
    - annotations.<name> — match any span annotation by name and value
    - annotations.feedback.<name> — match only feedback annotations
    - annotations.expectation.<name> — match only expectation annotations

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
    states: list[TraceState] | None = Query(default=None),
) -> PaginatedTraces:
    """
    search: An optional search by trace_id.
    filters: List of filter conditions, all AND-ed together. Supported fields:
    - trace_id / id — string ops: =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
    - state — =, !=, IN, NOT IN (values: "ok", "error", "in_progress", "unspecified")
    - execution_time — numeric ops: =, !=, >, >=, <, <= (nanoseconds)
    - span_count — numeric ops: =, !=, >, >=, <, <=
    - created_at — date ops: =, !=, >, >=, <, <= (ISO string)
    - evals — string ops: =, !=, LIKE, ILIKE, CONTAINS (matches eval_id)
    - attributes.<key> — string or numeric ops based on value
    - annotations.<name> — match any span annotation by name and value
    - annotations.feedback.<name> — match only feedback annotations
    - annotations.expectation.<name> — match only expectation annotations

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

    Supported fields:
    - **trace_id / id** — =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
    - **state** — =, !=, IN, NOT IN (values: "ok", "error", "in_progress", "unspecified")
    - **execution_time** — =, !=, >, >=, <, <= (nanoseconds)
    - **span_count** — =, !=, >, >=, <, <=
    - **created_at** — =, !=, >, >=, <, <= (ISO date string)
    - **evals** — =, !=, LIKE, ILIKE, CONTAINS (matches eval_id)
    - **attributes.<key>** — string or numeric ops based on value type
    - **annotations.<name>** — match any span annotation
    - **annotations.feedback.<name>** — match only feedback annotations
    - **annotations.expectation.<name>** — match only expectation annotations

    Examples:
     - trace_id LIKE "%abc%"
     - state = "error"
     - state IN ("ok", "error")
     - execution_time > 5
     - span_count >= 3
     - created_at > "2024-01-01"
     - evals = "eval-001"
     - attributes.http.method = "GET"
     - attributes.http.status_code >= 400
     - annotations.feedback.quality = "true"
     - state = "error" AND execution_time > 10
    """
    return experiments_handler.validate_traces_filter(filter_strings)


@experiments_traces_router.get("/{trace_id}", response_model=TraceDetails)
def get_trace(experiment_id: str, trace_id: str) -> TraceDetails:
    return experiments_handler.get_trace(experiment_id, trace_id)
