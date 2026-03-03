from luml.experiments.backends.sqlite import SQLiteBackend

from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiment_groups import (
    Group,
    GroupDetails,
    GroupsSortBy,
    PaginatedGroups,
    UpdateGroup,
)
from lumlflow.schemas.experiments import (
    ExperimentListed,
    PaginatedExperiments,
)
from lumlflow.settings import config


class ExperimentGroupsHandler:
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        self._db_path = db_path
        self.db = SQLiteBackend(self._db_path)

    def get_experiment_groups(
        self,
        limit: int = 100,
        cursor_str: str | None = None,
        sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> PaginatedGroups:
        try:
            result = self.db.list_groups_pagination(
                limit=limit,
                cursor_str=cursor_str,
                sort_by=sort_by.value,
                order=order.value,
                search=search,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return PaginatedGroups(
            items=[Group.model_validate(g) for g in result.items],
            cursor=result.cursor,
        )

    def get_experiment_group_details(self, group_id: str) -> GroupDetails:
        try:
            group = self.db.get_group(group_id)
            static_params = self.db.get_group_experiments_static_params_keys(group_id)
            dynamic_params = self.db.get_group_experiments_dynamic_metrics_keys(
                group_id
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if not group:
            raise NotFound("Group not found")

        return GroupDetails(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            tags=group.tags,
            last_modified=group.last_modified,
            experiments_static_params=static_params,
            experiments_dynamic_params=dynamic_params,
        )

    def delete_experiment_group(self, group_id: str) -> None:
        if not self.db.get_group(group_id):
            raise NotFound("Group not found")
        result = self.db.list_group_experiments_pagination(group_id, limit=1)
        if result.items:
            raise ApplicationError(
                "Cannot delete a group that has linked experiments", status_code=409
            )
        try:
            self.db.delete_group(group_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

    def update_experiment_group(self, group_id: str, body: UpdateGroup) -> Group:
        try:
            group = self.db.update_group(
                group_id,
                name=body.name,
                description=body.description,
                tags=body.tags,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if not group:
            raise NotFound("Group not found")

        return Group.model_validate(group)

    def list_group_experiments(
        self,
        group_id: str,
        limit: int = 100,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> PaginatedExperiments:
        try:
            group = self.db.get_group(group_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if not group:
            raise NotFound("Group not found")

        try:
            json_sort_column = self.db.resolve_experiment_sort_column(group_id, sort_by)
        except ValueError as e:
            raise ApplicationError(str(e), status_code=400) from e

        try:
            result = self.db.list_group_experiments_pagination(
                group_id,
                limit=limit,
                cursor_str=cursor_str,
                sort_by=sort_by,
                order=order.value,
                search=search,
                json_sort_column=json_sort_column,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return PaginatedExperiments(
            items=[ExperimentListed.model_validate(e) for e in result.items],
            cursor=result.cursor,
        )
