from luml.experiments.backends.sqlite import SQLiteBackend

from lumlflow.infra.exceptions import ApplicationError
from lumlflow.schemas.base import Cursor, SortOrder
from lumlflow.schemas.experiment_groups import Group, GroupsSortBy, PaginatedGroups
from lumlflow.schemas.experiments import (
    ExperimentSimple,
    PaginatedExperiments,
)
from lumlflow.settings import config
from lumlflow.utils.pagination import decode_cursor, get_cursor


class ExperimentGroupsHandler:
    def __init__(self, db_path: str | None = config.BACKEND_STORE_URI):
        self._db_path = db_path
        self.db = SQLiteBackend(self._db_path)

    @staticmethod
    def _validate_cursor(
        cursor: Cursor | None,
        sort_by: GroupsSortBy,
        order: SortOrder,
    ) -> Cursor | None:
        if cursor and (cursor.sort_by == sort_by.value and cursor.order == order.value):
            return cursor
        return None

    def get_experiment_groups(
        self,
        limit: int = 100,
        cursor_str: str | None = None,
        sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
        search: str | None = None,
    ) -> PaginatedGroups:
        cursor = decode_cursor(cursor_str)
        use_cursor = self._validate_cursor(cursor, sort_by, order)

        try:
            items = self.db.list_groups_pagination(
                limit=limit,
                cursor_id=str(use_cursor.id) if use_cursor else None,
                cursor_value=use_cursor.value if use_cursor else None,
                sort_by=str(sort_by.value),
                order=str(order.value),
                search=search,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return PaginatedGroups(
            items=[Group.model_validate(g) for g in items[:limit]],
            cursor=get_cursor(items, limit, str(sort_by), order),
        )

    def get_experiment_group(
        self,
        group_id,
        limit: int = 100,
        cursor_str: str | None = None,
        sort_by: GroupsSortBy = GroupsSortBy.CREATED_AT,
        order: SortOrder = SortOrder.DESC,
    ) -> PaginatedExperiments:
        cursor = decode_cursor(cursor_str)
        use_cursor = self._validate_cursor(cursor, sort_by, order)

        try:
            experiments = self.db.list_group_experiments_pagination(
                group_id,
                limit=limit,
                cursor_id=str(use_cursor.id) if use_cursor else None,
                cursor_value=use_cursor.value if use_cursor else None,
                sort_by=sort_by,
                order=order,
            )
        except Exception as e:
            raise ApplicationError(str(e), status_code=500) from e

        return PaginatedExperiments(
            items=[ExperimentSimple.model_validate(e) for e in experiments[:limit]],
            cursor=get_cursor(experiments, limit, str(sort_by), order),
        )
