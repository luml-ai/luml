from fastapi import APIRouter, Query

from lumlflow.handlers.experiment_groups import ExperimentGroupsHandler
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiment_groups import Group, GroupsSortBy, PaginatedGroups

experiment_groups_router = APIRouter(
    prefix="/experiment-groups",
    tags=["experiment-groups"],
)

groups_handler = ExperimentGroupsHandler()


@experiment_groups_router.get("", response_model=PaginatedGroups)
def get_experiment_groups(
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
    order: SortOrder = SortOrder.DESC,
) -> PaginatedGroups:
    return groups_handler.get_experiment_groups(
        limit=limit,
        cursor_str=cursor,
        sort_by=sort_by,
        order=order,
    )


@experiment_groups_router.get("/{group_id}", response_model=Group)
def get_experiment_group(group_id: str) -> Group | None:
    return groups_handler.get_experiment_group(group_id)
