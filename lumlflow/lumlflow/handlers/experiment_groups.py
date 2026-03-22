import re

from luml.experiments.tracker import ExperimentTracker

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
    SearchValidationResult,
)
from lumlflow.settings import get_tracker


class ExperimentGroupsHandler:
    def __init__(self, tracker: ExperimentTracker | None = None) -> None:
        self.tracker = tracker or get_tracker()

    @staticmethod
    def _natural_sort_key(s: str) -> list:
        return [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", s)]

    def get_experiment_groups(
        self,
        limit: int = 100,
        cursor_str: str | None = None,
        sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> PaginatedGroups:
        try:
            result = self.tracker.list_groups_pagination(
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
        group = self.tracker.get_group(group_id)

        if not group:
            raise NotFound("Group not found")

        try:
            static_params = self.tracker.get_group_experiments_static_params_keys(
                group_id
            )
            dynamic_params = self.tracker.get_group_experiments_dynamic_metrics_keys(
                group_id
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return GroupDetails(
            id=group.id,
            name=group.name,
            description=group.description,
            created_at=group.created_at,
            tags=group.tags,
            last_modified=group.last_modified,
            experiments_static_params=sorted(static_params, key=self._natural_sort_key),
            experiments_dynamic_params=sorted(
                dynamic_params, key=self._natural_sort_key
            ),
        )

    def get_groups_static_params_keys(self, groups_ids: list[str]) -> list[str]:
        static_params: set[str] = set()

        for group_id in groups_ids:
            if self.tracker.get_group(group_id):
                static_params.update(
                    self.tracker.get_group_experiments_static_params_keys(group_id)
                )

        return sorted(static_params, key=self._natural_sort_key)

    def get_groups_dynamic_metrics_keys(self, groups_ids: list[str]) -> list[str]:
        dynamic_metrics: set[str] = set()

        for group_id in groups_ids:
            if self.tracker.get_group(group_id):
                dynamic_metrics.update(
                    self.tracker.get_group_experiments_dynamic_metrics_keys(group_id)
                )

        return sorted(dynamic_metrics, key=self._natural_sort_key)

    def delete_experiment_group(self, group_id: str) -> None:
        if not self.tracker.get_group(group_id):
            raise NotFound("Group not found")

        result = self.tracker.list_group_experiments_pagination(group_id, limit=1)

        if result.items:
            raise ApplicationError(
                "Cannot delete a group that has linked experiments", status_code=409
            )
        try:
            self.tracker.delete_group(group_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

    def update_experiment_group(self, group_id: str, body: UpdateGroup) -> Group:
        try:
            group = self.tracker.update_group(
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

    def list_groups_experiments(
        self,
        group_ids: list[str],
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> PaginatedExperiments:
        json_sort_column: str | None = None
        if group_ids:
            try:
                json_sort_column = self.tracker.resolve_groups_experiment_sort_column(
                    group_ids, sort_by
                )
            except ValueError as e:
                raise ApplicationError(str(e), status_code=400) from e

        try:
            result = self.tracker.list_groups_experiments_pagination(
                group_ids,
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
            group = self.tracker.get_group(group_id)
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        if not group:
            raise NotFound("Group not found")

        try:
            json_sort_column = self.tracker.resolve_experiment_sort_column(
                group_id, sort_by
            )
        except ValueError as e:
            raise ApplicationError(str(e)) from e

        try:
            result = self.tracker.list_group_experiments_pagination(
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

    def validate_search(self, query: str | None) -> SearchValidationResult:
        try:
            self.tracker.validate_experiments_search(query)
        except Exception as e:
            return SearchValidationResult(valid=False, error=str(e))
        return SearchValidationResult(valid=True)
