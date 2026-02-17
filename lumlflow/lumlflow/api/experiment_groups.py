from fastapi import APIRouter, Query, status

from lumlflow.handlers.experiment_groups import ExperimentGroupsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiment_groups import (
    Group,
    GroupDetails,
    GroupsSortBy,
    PaginatedGroups,
    UpdateGroup,
)
from lumlflow.schemas.experiments import PaginatedExperiments, SearchValidationResult

experiment_groups_router = APIRouter(
    prefix="/api/experiment-groups",
    tags=["experiment-groups"],
)

groups_handler = ExperimentGroupsHandler()


@experiment_groups_router.get("", response_model=PaginatedGroups)
def get_experiment_groups(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
    sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
) -> PaginatedGroups:
    return groups_handler.get_experiment_groups(
        limit=limit,
        cursor_str=cursor,
        sort_by=sort_by,
        order=order,
        search=search,
    )


@experiment_groups_router.get("/{group_id}/details", response_model=GroupDetails)
def get_group_details(group_id: str) -> GroupDetails:
    return groups_handler.get_experiment_group_details(group_id)


@experiment_groups_router.patch("/{group_id}", response_model=Group)
def update_experiment_group(group_id: str, group: UpdateGroup) -> Group:
    return groups_handler.update_experiment_group(group_id, group)


@experiment_groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experiment_group(group_id: str) -> None:
    groups_handler.delete_experiment_group(group_id)


@experiment_groups_router.get(
    "/experiments/validate-search", response_model=SearchValidationResult
)
def validate_experiments_search(
    query: str | None = None,
) -> SearchValidationResult:
    """
    Validate a search query string without executing it.

    Supported filter syntax:
    - **Attributes** (bare key or attribute.<key> / attr.<key>):
      name, status, description, group_id — operators:
        =, !=, LIKE, ILIKE, CONTAINS, IN, NOT IN
      created_at, duration — operators: =, !=, >, >=, <, <=
    - **Dynamic metrics**: metric.<key> / metrics.<key> / dynamic_params.<key>
        — numeric operators: =, !=, >, >=, <, <=
    - **Static params**: param.<key> / params.<key> / static_params.<key>
        — operators: =, !=, LIKE, ILIKE, CONTAINS
    - **Tags**: tag / tags — operators: =, !=, LIKE, ILIKE, CONTAINS
    - **Logical**: AND, OR, grouping with (...)

    Examples:
     - tags ILIKE "%PROD%"
     - tags CONTAINS "staging"
     - status IN ("active", "completed")
     - status NOT IN ("deleted",)
     - description LIKE "%experiment%"
     - duration > 60
     - created_at > "2024-01-01"
     - tags CONTAINS "prod" OR tags CONTAINS "production"
     - (tags LIKE "%production%" OR tags LIKE "%prod%")
        AND status != "deleted" AND metric.accuracy > 0.85
     - (name CONTAINS "1" OR tags LIKE "%production%") AND status = "completed"
        AND dynamic_params.metric_87 > 0.3 AND dynamic_params.metric_87 < 0.4
     - ((param.lr = 0.001 OR param.lr = 0.01) AND metric.accuracy > 0.88)
        OR (tags LIKE "%staging%" AND status = "completed")
    """
    return groups_handler.validate_search(query)


@experiment_groups_router.get(
    "/{group_id}/experiments", response_model=PaginatedExperiments
)
def get_group_experiments(
    group_id: str,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
    sort_by: str = "created_at",
    order: SortOrder = SortOrder.DESC,
    search: str | None = None,
) -> PaginatedExperiments:
    return groups_handler.list_group_experiments(
        group_id,
        limit=limit,
        cursor_str=cursor,
        sort_by=sort_by,
        order=order,
        search=search,
    )


@experiment_groups_router.get("/{group_id}", response_model=PaginatedExperiments)
def get_group_experiments(group_id: str) -> PaginatedExperiments:
    return groups_handler.get_experiment_group(group_id)
