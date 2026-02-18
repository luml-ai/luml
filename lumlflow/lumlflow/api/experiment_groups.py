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
from lumlflow.schemas.experiments import PaginatedExperiments

experiment_groups_router = APIRouter(
    prefix="/experiment-groups",
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
    return groups_handler.get_experiment_group(
        group_id,
        limit=limit,
        cursor_str=cursor,
        sort_by=sort_by,
        order=order,
        search=search,
    )
