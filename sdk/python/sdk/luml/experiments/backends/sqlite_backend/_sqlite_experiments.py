# flake8: noqa: E501
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    pass


from sdk.luml.artifacts._base import DiskFile, _BaseFile
from sdk.luml.experiments.backends._cursor import Cursor
from sdk.luml.experiments.backends.data_types import (
    Experiment,
    ExperimentData,
    ExperimentMetaData,
    Group,
    PaginatedResponse,
)
from sdk.luml.experiments.backends.sqlite_backend._sqlite_base import _SQLiteBase
from sdk.luml.utils.tar import create_and_index_tar

from luml.experiments.backends._search_utils import (
    SearchExperimentsUtils,
)


class SQLiteGroupMixin(_SQLiteBase):
    def _build_experiments_page(
        self,
        where_conditions: list[tuple[str, list]],
        limit: int,
        sort_by: str,
        order: str,
        cursor_str: str | None,
        json_sort_column: str | None,
    ) -> PaginatedResponse[Experiment]:
        allowed_json_columns = {"static_params", "dynamic_params"}
        if json_sort_column is not None:
            if json_sort_column not in allowed_json_columns:
                raise ValueError(
                    f"json_sort_column must be one of {allowed_json_columns}"
                )
            order = order.lower()
            if order not in ("asc", "desc"):
                order = "desc"
        else:
            sort_by, order = self._sanitize_pagination_params(
                sort_by, order, self._STANDARD_EXPERIMENT_SORT_COLUMNS
            )

        use_cursor = Cursor.decode_and_validate(cursor_str, sort_by, order)
        conn = self._get_meta_connection()

        cursor_value = None
        if use_cursor and use_cursor.value is not None:
            val = use_cursor.value
            if isinstance(val, datetime):
                cursor_value = val.astimezone(UTC).isoformat()
            else:
                cursor_value = str(val)

        rows = self._execute_paginated_query(
            conn=conn,
            table="experiments",
            columns=self._EXPERIMENT_COLUMNS,
            limit=limit,
            sort_by=sort_by,
            order=order,
            cursor_id=use_cursor.id if use_cursor else None,
            cursor_value=cursor_value,
            where=where_conditions,
            json_sort_column=json_sort_column,
            allowed_sort_columns=self._STANDARD_EXPERIMENT_SORT_COLUMNS,
        )

        experiments_dicts = self._items_to_dict(self._EXPERIMENT_COLUMNS, rows)
        models_by_experiment = self.list_batch_experiments_models(
            [e["id"] for e in experiments_dicts]
        )

        group_ids = list({e["group_id"] for e in experiments_dicts if e["group_id"]})
        group_names: dict[str, str] = {}
        if group_ids:
            placeholders = ",".join("?" * len(group_ids))
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT id, name FROM experiment_groups WHERE id IN ({placeholders})",
                group_ids,
            )
            group_names = {row[0]: row[1] for row in cursor.fetchall()}

        items = [
            Experiment(
                id=e["id"],
                group_id=e["group_id"],
                group_name=group_names.get(e["group_id"]),
                name=e["name"],
                created_at=e["created_at"],
                status=e["status"],
                tags=e["tags"] if e["tags"] else [],
                models=models_by_experiment.get(e["id"], []),
                duration=e["duration"],
                description=e["description"],
                static_params=e["static_params"] or None,
                dynamic_params=e["dynamic_params"] or None,
            )
            for e in experiments_dicts
        ]
        return PaginatedResponse(
            items=items[:limit],
            cursor=Cursor.get_cursor(items, limit, sort_by, order, json_sort_column),
        )

    def create_group(
        self,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Group:
        """
        Creates or retrieves an existing experiment group from the database.

        This method checks if a group with the specified name exists. If it exists, it retrieves
        the existing group data and returns it. Otherwise, it creates a new group in the database,
        commits the changes, and returns the newly created group.

        Args:
            name: The name of the experiment group to create or retrieve.
            description: Optional. Additional details about the group. If not provided, defaults to None.
            tags: Optional list of tags for the group.

        Returns:
            Group: An instance of the Group class containing the data for the retrieved or newly created group.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, description, created_at, tags, last_modified "
            "FROM experiment_groups WHERE name = ?",
            (name,),
        )
        existing = cursor.fetchone()
        if existing:
            return Group(
                id=existing[0],
                name=existing[1],
                description=existing[2],
                created_at=existing[3],
                tags=json.loads(existing[4]) if existing[4] else [],
                last_modified=existing[5],
            )

        group_id = str(uuid.uuid4())
        tags_str = json.dumps(tags) if tags else None
        cursor.execute(
            "INSERT INTO experiment_groups (id, name, description, tags) VALUES (?, ?, ?, ?)",
            (group_id, name, description, tags_str),
        )
        conn.commit()
        return Group(
            id=group_id,
            name=name,
            description=description,
            created_at=datetime.now(UTC),
            tags=tags or [],
            last_modified=datetime.now(UTC),
        )

    def update_group(
        self,
        group_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Group | None:
        """
        Updates the attributes of an existing group identified by its group ID. If no
        updates are provided, the method retrieves the existing group's details.

        Args:
            group_id: The unique identifier of the group to be updated.
            name: The new name of the group. If None, the name remains unchanged.
            description: The new description of the group. If None, the description
                remains unchanged.
            tags: A list of new tags associated with the group. If None, the tags
                remain unchanged.

        Returns:
            An updated Group object if the update is successful. If there are no
            updates provided, or the group ID doesn't exist, returns None.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        fields: list[str] = []
        values: list[Any] = []

        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if description is not None:
            fields.append("description = ?")
            values.append(description)
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags))

        if not fields:
            return self.get_group(group_id)

        fields.append("last_modified = CURRENT_TIMESTAMP")
        values.append(group_id)

        cursor.execute(
            f"UPDATE experiment_groups SET {', '.join(fields)} WHERE id = ?",  # noqa: S608
            values,
        )
        conn.commit()

        return self.get_group(group_id)

    def delete_group(self, group_id: str) -> None:
        """
        Deletes a group and all its experiments from the database, including
        their associated files and directories on the filesystem.

        Args:
            group_id (str): The unique identifier of the group to be deleted.

        Returns:
            None
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM experiments WHERE group_id = ?", (group_id,))
        experiment_ids = [row[0] for row in cursor.fetchall()]

        for experiment_id in experiment_ids:
            self.delete_experiment(experiment_id)

        cursor.execute("DELETE FROM experiment_groups WHERE id = ?", (group_id,))
        conn.commit()

    def list_groups(self) -> list[Group]:  # noqa: ANN401
        """
        Retrieves a list of all experiment groups from the database and returns them as a list
        of `Group` objects. Each group contains metadata including its ID, name, description,
        and creation date.

        Returns:
            list[Group]: A list of `Group` objects representing all experiment groups in the
            database.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.list_groups()
            [
                Group(
                    id="group-123",
                    name="cv_experiments",
                    description="Computer vision experiments",
                    created_at=datetime(2024, 6, 1, 10, 0, 0),
                    tags=["cv", "production"],
                    last_modified=datetime(2024, 6, 5, 15, 30, 0),
                ),
                Group(
                    id="group-456",
                    name="nlp_experiments",
                    description=None,
                    created_at=datetime(2024, 6, 2, 8, 0, 0),
                    tags=[],
                    last_modified=None,
                ),
            ]
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, created_at, tags, last_modified FROM experiment_groups"
        )
        groups = []
        for row in cursor.fetchall():
            groups.append(
                Group(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    created_at=row[3],
                    tags=json.loads(row[4]) if row[4] else [],
                    last_modified=row[5],
                )
            )
        return groups

    def list_groups_pagination(
        self,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        search: str | None = None,
    ) -> PaginatedResponse[Group]:
        """
        Retrieves a paginated list of experiment groups from the database. Supports optional
        filtering, sorting, and cursor-based pagination mechanisms to improve query efficiency
        and usability.

        Args:
            limit (int): The maximum number of items to include in the response. Defaults to 20.
            cursor_str (str | None): An optional encoded cursor string to specify the starting
                point for the query. Used for cursor-based pagination.
            sort_by (str): The attribute by which to sort the results. Must be one of
                "created_at", "name", or "last_modified". Defaults to "created_at".
            order (str): The sort order for the results. Must be either "asc" or "desc".
                Defaults to "desc".
            search (str | None): An optional search term to filter groups based on name or tags.

        Returns:
            PaginatedResponse[Group]: A paginated response object containing a list of
                Group objects and pagination metadata.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.list_groups_pagination(limit=2, sort_by="created_at", order="desc")
            PaginatedResponse(
                items=[
                    Group(
                        id="group-123",
                        name="cv_experiments",
                        description="Computer vision experiments",
                        created_at=datetime(2024, 6, 2, 10, 0, 0),
                        tags=["cv", "production"],
                        last_modified=datetime(2024, 6, 5, 15, 30, 0),
                    ),
                    Group(
                        id="group-456",
                        name="nlp_experiments",
                        description=None,
                        created_at=datetime(2024, 6, 1, 8, 0, 0),
                        tags=[],
                        last_modified=None,
                    ),
                ],
                cursor="eyJjcmVhdGVkX2F0IjogIjIwMjQtMDYtMDEifQ==",
            )
        """
        sort_by, order = self._sanitize_pagination_params(
            sort_by,
            order,
            {"created_at", "name", "description", "last_modified"},
        )

        use_cursor = Cursor.decode_and_validate(cursor_str, sort_by, order)

        conn = self._get_meta_connection()
        columns = ["id", "name", "description", "created_at", "tags", "last_modified"]
        where_conditions = []

        if search:
            where_conditions.append(
                (
                    "id LIKE ? OR name LIKE ? OR tags LIKE ?",
                    [f"%{search}%"] * 3,
                )
            )

        rows = self._execute_paginated_query(
            conn=conn,
            table="experiment_groups",
            columns=columns,
            limit=limit,
            sort_by=sort_by,
            order=order,
            cursor_id=use_cursor.id if use_cursor else None,
            cursor_value=use_cursor.value if use_cursor else None,
            where=where_conditions,
            allowed_sort_columns={"created_at", "name", "description", "last_modified"},
        )

        items = [
            Group(
                id=d["id"],
                name=d["name"],
                description=d["description"],
                created_at=d["created_at"],
                tags=d["tags"] or [],
                last_modified=d["last_modified"],
            )
            for d in self._items_to_dict(columns, rows)
        ]
        return PaginatedResponse(
            items=items[:limit],
            cursor=Cursor.get_cursor(items, limit, sort_by, order),
        )

    def get_group(self, group_id: str) -> Group | None:  # noqa: ANN401
        """
        Retrieves information about an experiment group by its unique identifier.

        This method queries the database for an experiment group with the provided
        group identifier. If the group exists, it returns a `Group` object populated
        with the group's details. Otherwise, it returns `None`.

        Args:
            group_id (str): A unique identifier for the experiment group.

        Returns:
            Group | None: A `Group` object containing the details of the experiment
            group if found, otherwise `None`.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_group("group-123")
            Group(
                id="group-123",
                name="cv_experiments",
                description="Computer vision experiments",
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                tags=["cv", "production"],
                last_modified=datetime(2024, 6, 5, 15, 30, 0),
            )

            >>> backend.get_group("nonexistent-id")
            None
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, created_at, tags, last_modified "
            "FROM experiment_groups WHERE id = ?",
            (group_id,),
        )

        if row := cursor.fetchone():
            return Group(
                id=row[0],
                name=row[1],
                description=row[2],
                created_at=row[3],
                tags=json.loads(row[4]) if row[4] else [],
                last_modified=row[5],
            )
        return None

    def list_group_experiments_pagination(
        self,
        group_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: Literal["asc", "desc"] = "desc",
        search: str | None = None,
        json_sort_column: Literal["static_params", "dynamic_params"] | None = None,
    ) -> PaginatedResponse[Experiment]:
        """
        Fetches a paginated list of experiments within a specified group, supporting various
        sorting, filtering, and cursor-based pagination options.

        This method retrieves experiments associated with a specific group ID, ordering and
        filtering them based on the provided parameters. It supports sorting by both standard
        columns and specific JSON fields, as well as filtering based on search terms and
        integrating with a cursor-based pagination approach.

        Args:
            group_id (str): The unique identifier for the group whose experiments are being
                listed.
            limit (int, optional): The maximum number of records to retrieve per page. Default
                is 20.
            cursor_str (str | None, optional): The encoded cursor string for implementing
                pagination. Default is None.
            sort_by (str, optional): The column name to sort the results by. Default is
                "created_at".
            order (str, optional): The order of sorting, either "asc" (ascending) or "desc"
                (descending). Default is "desc".
            search (str | None, optional): The search string for filtering experiments by name
                or tags. Default is None.
            json_sort_column (str | None, optional): A JSON column (either "static_params" or
                "dynamic_params") to use for sorting. Default is None.

        Returns:
            PaginatedResponse[Experiment]: A paginated response object containing the list of
                Experiment objects and pagination-related metadata.

        Raises:
            ValueError: If the provided `json_sort_column` is not one of the allowed values
                ("static_params", "dynamic_params").

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> response = backend.list_group_experiments_pagination(
            ...     group_id="group-123",
            ...     limit=2,
            ...     sort_by="created_at",
            ...     order="desc",
            ... )
            PaginatedResponse(
                items=[
                    Experiment(
                        id="exp-001",
                        name="baseline_run",
                        status="completed",
                        created_at=datetime(2024, 6, 1, 12, 0, 0),
                        tags=["baseline", "v1"],
                        models=[],
                        duration=42.3,
                        description="Initial baseline experiment",
                        group_id="group-123",
                        static_params={"lr": 0.01, "epochs": 10},
                        dynamic_params={"loss": 0.25, "accuracy": 0.91},
                    )
                ],
                cursor="eyJjcmVhdGVkX2F0IjogIjIwMjQtMDYtMDIifQ=="
            )
        """
        where_conditions: list[tuple[str, list]] = [("group_id = ?", [group_id])]
        if search:
            where_clause, _, search_params = SearchExperimentsUtils.to_sql(search)
            if where_clause:
                where_conditions.append((where_clause, search_params))
        return self._build_experiments_page(
            where_conditions, limit, sort_by, order, cursor_str, json_sort_column
        )

    def list_groups_experiments_pagination(
        self,
        group_ids: list[str],
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: Literal["asc", "desc"] = "desc",
        search: str | None = None,
        json_sort_column: Literal["static_params", "dynamic_params"] | None = None,
    ) -> PaginatedResponse[Experiment]:
        """
        Fetches a paginated list of experiments across multiple groups, supporting
        various sorting, filtering, and cursor-based pagination options.

        This method retrieves experiments associated with the provided group IDs,
        ordering and filtering them based on the given parameters. It supports sorting
        by both standard columns and specific JSON fields, as well as filtering based
        on search terms and cursor-based pagination. Returns an empty response
        if the group list is empty.

        Args:
            group_ids (list[str]): The list of group identifiers whose experiments are
                being listed.
            limit (int, optional): The maximum number of records to retrieve per page.
                Default is 20.
            cursor_str (str | None, optional): The encoded cursor string for
                implementing pagination. Default is None.
            sort_by (str, optional): The column name to sort the results by. Default is
                "created_at".
            order (str, optional): The order of sorting, either "asc" (ascending) or
                "desc" (descending). Default is "desc".
            search (str | None, optional): The search string for filtering experiments
                by name or tags. Default is None.
            json_sort_column (str | None, optional): A JSON column (either
                "static_params" or "dynamic_params") to use for sorting. Default is None

        Returns:
            PaginatedResponse[Experiment]: A paginated response object containing the
                list of Experiment objects and pagination-related metadata.

        Raises:
            ValueError: If the provided `json_sort_column` is not one of the allowed
                values ("static_params", "dynamic_params").

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> response = backend.list_groups_experiments_pagination(
            ...     group_ids=["group-123", "group-456"],
            ...     limit=2,
            ...     sort_by="created_at",
            ...     order="desc",
            ... )
            PaginatedResponse(
                items=[
                    Experiment(
                        id="exp-001",
                        name="baseline_run",
                        status="completed",
                        created_at=datetime(2024, 6, 1, 12, 0, 0),
                        tags=["baseline", "v1"],
                        models=[],
                        duration=42.3,
                        description="Initial baseline experiment",
                        group_id="group-123",
                        static_params={"lr": 0.01, "epochs": 10},
                        dynamic_params={"loss": 0.25, "accuracy": 0.91},
                    )
                ],
                cursor="eyJjcmVhdGVkX2F0IjogIjIwMjQtMDYtMDIifQ=="
            )
        """
        if not group_ids:
            return PaginatedResponse(items=[], cursor=None)
        placeholders = ",".join("?" * len(group_ids))
        where_conditions: list[tuple[str, list]] = [
            (f"group_id IN ({placeholders})", list(group_ids))
        ]
        if search:
            where_clause, _, search_params = SearchExperimentsUtils.to_sql(search)
            if where_clause:
                where_conditions.append((where_clause, search_params))
        return self._build_experiments_page(
            where_conditions, limit, sort_by, order, cursor_str, json_sort_column
        )


class SQLiteExperimentMixin(SQLiteGroupMixin):
    @staticmethod
    def validate_experiments_search(search: str | None = None) -> None:
        return SearchExperimentsUtils.validate_filter_string(search)

    def resolve_experiment_sort_column(self, group_id: str, sort_by: str) -> str | None:
        """
        Resolves the json_sort_column for list_group_experiments_pagination.

        Specific to experiments: checks dynamic_params and static_params keys.
        - None              → sort_by is a standard experiment column
        - "dynamic_params"  → sort_by is a dynamic metric key
        - "static_params"   → sort_by is a static param key
        - raises ValueError → sort_by is unknown
        """
        if sort_by in self._STANDARD_EXPERIMENT_SORT_COLUMNS:
            return None
        if sort_by in self.get_group_experiments_dynamic_metrics_keys(group_id):
            return "dynamic_params"
        if sort_by in self.get_group_experiments_static_params_keys(group_id):
            return "static_params"
        raise ValueError(
            f"Invalid sort_by '{sort_by}'. Must be one of "
            f"{sorted(self._STANDARD_EXPERIMENT_SORT_COLUMNS)} "
            "or a valid dynamic metric / static param key."
        )

    def initialize_experiment(
        self,
        experiment_id: str,
        group: str = "default",
        name: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
        source: str | None = None,
    ) -> None:
        """
        Initializes an experiment by associating it with a group and storing its
        metadata in the database.

        Args:
            experiment_id: Unique identifier for the experiment.
            group: Group name to which the experiment belongs. If the group does not
                exist, it will be created. Defaults to "Default group".
            name: Optional name of the experiment. If not provided, the `experiment_id`
                will be used as the name.
            tags: Optional list of tags associated with the experiment.
            description: Optional description of the experiment.
            source: Path of the script or file that created the experiment.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM experiment_groups WHERE name = ?", (group,))

        if row := cursor.fetchone():
            group_id = row[0]
        else:
            created_group = self.create_group(group)
            group_id = created_group.id

        tags_str = json.dumps(tags) if tags else None
        cursor.execute(
            """
            INSERT OR REPLACE INTO experiments (id, name, group_id, tags, description, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (experiment_id, name or experiment_id, group_id, tags_str, description, source),
        )

        conn.commit()

        self._initialize_experiment_db(experiment_id)
        self.pool.mark_experiment_active(experiment_id)

    def log_static(self, experiment_id: str, key: str, value: Any) -> None:  # noqa: ANN401
        """
        Logs a static parameter to the database for a given experiment.

        This method logs a static parameter with a specified key and value to the
        associated experiment. The parameter can be of type string, integer, float,
        boolean, or any other data structure that can be serialized into JSON.
        If a static parameter with the same key already exists, it will be updated.

        Args:
            experiment_id (str): The unique identifier of the experiment for which the
                static parameter is being logged.
            key (str): The key associated with the static parameter.
            value (Any): The value of the static parameter. It can be of type string,
                integer, float, boolean, or any serializable object.
        """
        self._ensure_experiment_initialized(experiment_id)

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        if isinstance(value, str | int | float | bool):
            value_str = str(value)
            value_type = type(value).__name__
        else:
            value_str = json.dumps(value)
            value_type = "json"

        cursor.execute(
            """
            INSERT OR REPLACE INTO static_params (key, value, value_type)
            VALUES (?, ?, ?)
        """,
            (key, value_str, value_type),
        )

        conn.commit()

    def log_dynamic(
        self, experiment_id: str, key: str, value: int | float, step: int | None = None
    ) -> None:
        """
        Logs a dynamic metric for a given experiment. This method allows updating or
        tracking metrics like performance indicators over multiple steps for analysis.

        Args:
            experiment_id (str): Identifier for the experiment where the metric will
                be stored. It must be a valid experiment ID initialized beforehand.
            key (str): The label or name of the metric being recorded. Used to
                differentiate between various tracked metrics.
            value (int | float): Numeric value of the metric being logged. Must be
                either an integer or a float.
            step (int | None, optional): The specific step number associated with this
                value. If not provided, the method defaults to the next available
                step, determined by the maximum recorded step for the specified key.

        Returns:
            None
        """
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()
        if step is None:
            cursor.execute(
                "SELECT MAX(step) FROM dynamic_metrics WHERE key = ?", (key,)
            )
            result = cursor.fetchone()
            step = (result[0] or -1) + 1

        cursor.execute(
            """
            INSERT OR REPLACE INTO dynamic_metrics (key, value, step)
            VALUES (?, ?, ?)
        """,
            (key, float(value), step),
        )

        conn.commit()

    def get_experiment_data(self, experiment_id: str) -> ExperimentData:  # noqa: ANN401, C901
        """
        Retrieves and constructs the experiment data for a specified experiment ID from
        the corresponding database. It encompasses metadata, static parameters,
        dynamic metrics, and attachments associated with the experiment.

        Args:
            experiment_id (str): Unique identifier for the experiment.

        Returns:
            ExperimentData: An object containing all experiment data, including
            metadata, static parameters, dynamic metrics, and attachments.

        Raises:
            ValueError: If the experiment with the given experiment ID is not found.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")

        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        cursor.execute("SELECT key, value, value_type FROM static_params")
        static_params = {}
        for key, value, value_type in cursor.fetchall():
            static_params[key] = self._convert_static_param_value(value, value_type)

        cursor.execute(
            "SELECT key, value, step FROM dynamic_metrics ORDER BY key, step"
        )
        dynamic_metrics: dict[str, list[dict[str, Any]]] = {}
        for key, value, step in cursor.fetchall():
            if key not in dynamic_metrics:
                dynamic_metrics[key] = []
            dynamic_metrics[key].append({"value": value, "step": step})

        cursor.execute("SELECT name, file_path, created_at FROM attachments")
        attachments = {}
        for name, file_path, created_at in cursor.fetchall():
            attachments[name] = {
                "file_path": file_path,
                "created_at": created_at,
            }

        meta_conn = self._get_meta_connection()
        meta_cursor = meta_conn.cursor()
        meta_cursor.execute(
            "SELECT name, created_at, status, group_id, tags, duration, description "
            "FROM experiments WHERE id = ?",
            (experiment_id,),
        )
        meta_row = meta_cursor.fetchone()

        metadata = {}
        if meta_row:
            metadata = ExperimentMetaData(
                name=meta_row[0],
                created_at=meta_row[1],
                status=meta_row[2],
                group_id=meta_row[3],
                tags=json.loads(meta_row[4]) if meta_row[4] else [],
                duration=meta_row[5],
                description=meta_row[6],
            )

        return ExperimentData(
            experiment_id=experiment_id,
            metadata=metadata,
            static_params=static_params,
            dynamic_metrics=dynamic_metrics,
            attachments=attachments,
        )

    def list_experiments(self) -> list[Experiment]:  # noqa: ANN401
        """
        Retrieves and returns a list of all experiments stored in the database.

        The method queries the database to fetch experiment details such as
        ID, name, creation date, status, group ID, associated tags, static
        parameters, and dynamic parameters. The information is used to construct
        a list of `Experiment` objects which represent the stored experiments.

        Returns:
            list[Experiment]: A list of `Experiment` objects containing information
            about each experiment retrieved from the database.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, created_at, status, group_id, tags, static_params, dynamic_params, duration, description
            FROM experiments
            """
        )
        experiments = []
        for row in cursor.fetchall():
            experiments.append(
                Experiment(
                    id=row[0],
                    name=row[1],
                    created_at=row[2],
                    status=row[3],
                    group_id=row[4],
                    tags=json.loads(row[5]) if row[5] else [],
                    static_params=json.loads(row[6]) if row[6] else {},
                    dynamic_params=json.loads(row[7]) if row[7] else {},
                    duration=row[8],
                    description=row[9],
                )
            )
        return experiments

    def get_group_experiments_static_params_keys(self, group_id: str) -> list[str]:
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM experiments WHERE group_id = ?", (group_id,))
        experiment_ids = [row[0] for row in cursor.fetchall()]

        keys: set[str] = set()
        for experiment_id in experiment_ids:
            db_path = self._get_experiment_db_path(experiment_id)
            if not db_path.exists():
                continue
            exp_conn = self._get_experiment_connection(experiment_id)
            exp_cursor = exp_conn.cursor()
            exp_cursor.execute("SELECT DISTINCT key FROM static_params")
            keys.update(row[0] for row in exp_cursor.fetchall())

        return sorted(keys)

    def get_group_experiments_dynamic_metrics_keys(self, group_id: str) -> list[str]:
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM experiments WHERE group_id = ?", (group_id,))
        experiment_ids = [row[0] for row in cursor.fetchall()]

        keys: set[str] = set()
        for experiment_id in experiment_ids:
            db_path = self._get_experiment_db_path(experiment_id)
            if not db_path.exists():
                continue
            exp_conn = self._get_experiment_connection(experiment_id)
            exp_cursor = exp_conn.cursor()
            exp_cursor.execute("SELECT DISTINCT key FROM dynamic_metrics")
            keys.update(row[0] for row in exp_cursor.fetchall())

        return sorted(keys)

    def resolve_groups_experiment_sort_column(
        self, group_ids: list[str], sort_by: str
    ) -> str | None:
        """
        Resolves the json_sort_column for list_groups_experiments_pagination.

        Checks across all provided groups.
        - None              → sort_by is a standard experiment column
        - "dynamic_params"  → sort_by is a dynamic metric key in any group
        - "static_params"   → sort_by is a static param key in any group
        - raises ValueError → sort_by is unknown across all groups
        """
        if sort_by in self._STANDARD_EXPERIMENT_SORT_COLUMNS:
            return None
        for group_id in group_ids:
            if sort_by in self.get_group_experiments_dynamic_metrics_keys(group_id):
                return "dynamic_params"
            if sort_by in self.get_group_experiments_static_params_keys(group_id):
                return "static_params"
        raise ValueError(
            f"Invalid sort_by '{sort_by}'. Must be one of "
            f"{sorted(self._STANDARD_EXPERIMENT_SORT_COLUMNS)} "
            "or a valid dynamic metric / static param key."
        )

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """
        Fetches an experiment's details from the database by the given experiment ID.

        This method queries the database to retrieve information about a specific
        experiment based on its unique identifier. If no experiment is found,
        the method returns None.

        Args:
            experiment_id (str): The unique identifier of the experiment to retrieve.

        Returns:
            Experiment | None: An instance of the `Experiment` class containing the
            details of the experiment if found, or None if no matching record exists.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT e.id, e.name, e.created_at, e.status, e.tags, e.duration, e.description, "
            "e.group_id, e.static_params, e.dynamic_params, eg.name AS group_name "
            "FROM experiments e "
            "LEFT JOIN experiment_groups eg ON e.group_id = eg.id "
            "WHERE e.id = ?",
            (experiment_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Experiment(
            id=row[0],
            name=row[1],
            created_at=row[2],
            status=row[3],
            tags=json.loads(row[4]) if row[4] else [],
            duration=row[5],
            description=row[6],
            group_id=row[7],
            static_params=json.loads(row[8]) if row[8] else None,
            dynamic_params=json.loads(row[9]) if row[9] else None,
            group_name=row[10],
        )

    def delete_experiment(self, experiment_id: str) -> None:
        """
        Deletes a specified experiment from the database and cleans up associated files
        from the filesystem.

        This method performs the following actions:
          1. Deletes the experiment record from the database.
          2. Marks the experiment as inactive in the experiment pool.
          3. Deletes all associated files and directories for the experiment if they
             exist on the filesystem.

        Args:
            experiment_id (str): The unique identifier of the experiment to delete.
        """
        exp_dir = self._get_experiment_dir(experiment_id)
        if exp_dir.exists():
            import shutil

            shutil.rmtree(exp_dir)

        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()

        self.pool.mark_experiment_inactive(experiment_id)

    def update_experiment(
        self,
        experiment_id: str,
        name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Experiment | None:
        """
        Updates an existing experiment record in the database. Fields such as name,
        description, and tags can be updated selectively. If no fields are updated,
        the function retrieves the current experiment details.

        Args:
            experiment_id: Unique identifier of the experiment to update.
            name: Optional new name for the experiment.
            description: Optional new description for the experiment.
            tags: Optional list of new tags associated with the experiment.

        Returns:
            Experiment: Updated experiment object if the update is successful
                or the record is retrieved.
            None: If the experiment with the given ID does not exist.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        fields: list[str] = []
        values: list[Any] = []

        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if description is not None:
            fields.append("description = ?")
            values.append(description)
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags))

        if not fields:
            cursor.execute(
                "SELECT id, name, created_at, status, tags, duration, description, "
                "group_id FROM experiments WHERE id = ?",
                (experiment_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return Experiment(
                id=row[0],
                name=row[1],
                created_at=row[2],
                status=row[3],
                tags=json.loads(row[4]) if row[4] else [],
                duration=row[5],
                description=row[6],
                group_id=row[7],
            )

        values.append(experiment_id)
        cursor.execute(
            f"UPDATE experiments SET {', '.join(fields)} WHERE id = ?",  # noqa: S608
            values,
        )
        conn.commit()

        cursor.execute(
            "SELECT id, name, created_at, status, tags, duration, description, group_id FROM experiments WHERE id = ?",
            (experiment_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Experiment(
            id=row[0],
            name=row[1],
            created_at=row[2],
            status=row[3],
            tags=json.loads(row[4]) if row[4] else [],
            duration=row[5],
            description=row[6],
            group_id=row[7],
        )

    def fail_experiment(self, experiment_id: str) -> None:
        meta_conn = self._get_meta_connection()
        meta_cursor = meta_conn.cursor()
        meta_cursor.execute(
            """
            UPDATE experiments
            SET status = 'error',
                duration = (julianday('now') - julianday(created_at)) * 86400.0
            WHERE id = ?
            """,
            (experiment_id,),
        )
        meta_conn.commit()
        self.pool.mark_experiment_inactive(experiment_id)

    def end_experiment(self, experiment_id: str) -> None:
        """
        Finalizes the experiment by setting its status to 'completed' and saving its
        static and dynamic parameters.

        This method fetches the relevant parameters for the experiment from the database
        and updates its status and associated values in the metadata store. It ensures
        resource cleanup by marking the experiment as inactive in the connection pool.

        Args:
            experiment_id (str): The unique identifier of the experiment to be finalized
        """
        exp_conn = self._get_experiment_connection(experiment_id)
        exp_cursor = exp_conn.cursor()

        exp_cursor.execute("SELECT key, value, value_type FROM static_params")
        static_params = {}
        for key, value, value_type in exp_cursor.fetchall():
            static_params[key] = self._convert_static_param_value(value, value_type)

        exp_cursor.execute(
            """
            SELECT key, value FROM dynamic_metrics dm1
            WHERE step = (
                SELECT MAX(step) FROM dynamic_metrics dm2 WHERE dm2.key = dm1.key
            )
            """
        )
        dynamic_params = dict(exp_cursor.fetchall())

        meta_conn = self._get_meta_connection()
        meta_cursor = meta_conn.cursor()
        meta_cursor.execute(
            """
            UPDATE experiments
            SET status = 'completed',
                static_params = ?,
                dynamic_params = ?,
                duration = (julianday('now') - julianday(created_at)) * 86400.0
            WHERE id = ?
            """,
            (
                json.dumps(static_params) if static_params else None,
                json.dumps(dynamic_params) if dynamic_params else None,
                experiment_id,
            ),
        )

        meta_cursor.execute(
            """
            UPDATE experiment_groups
            SET last_modified = CURRENT_TIMESTAMP
            WHERE id = (SELECT group_id FROM experiments WHERE id = ?)
            """,
            (experiment_id,),
        )

        meta_conn.commit()

        self.pool.mark_experiment_inactive(experiment_id)

    def export_experiment_db(self, experiment_id: str) -> DiskFile:
        """
        Exports the database file associated with the specified experiment.

        This method retrieves the database file path for the given experiment ID.
        It ensures the database exists and performs a write-ahead log (WAL)
        checkpoint to truncate the log before returning the database file. The
        method raises an error if the specified experiment cannot be found.

        Args:
            experiment_id (str): The unique identifier of the experiment whose
                database file needs to be exported.

        Returns:
            DiskFile: An object representing the exported database file.

        Raises:
            ValueError: If the experiment with the given experiment ID does not
                exist.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")
        with sqlite3.connect(db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        return DiskFile(db_path)

    def export_attachments(
        self, experiment_id: str
    ) -> tuple[_BaseFile, _BaseFile] | None:
        """
        Exports attachments associated with a specific experiment.

        This function retrieves, archives, and indexes the attachments of a specified
        experiment by creating a tarball. Depending on the presence of attachments,
        it may return created files or None.

        Args:
            experiment_id (str): The unique identifier of the experiment whose
                attachments need to be exported.

        Returns:
            tuple[_BaseFile, _BaseFile] | None: A tuple containing the created tarball
                and index file if attachments exist, or `None` if no attachments are
                found.
        """
        return create_and_index_tar(self._get_attachments_dir(experiment_id))

    def get_experiment_metric_history(
        self, experiment_id: str, key: str
    ) -> list[dict[str, Any]]:
        """
        Retrieves the historical metrics data for a specific experiment and metric key.
        The data is ordered by the step value in ascending order. Each metric record
        contains the value, step, and timestamp when the metric was logged.

        Args:
            experiment_id: The unique identifier for the experiment whose metric
                history is being retrieved.
            key: The key for the metric whose history is being fetched.

        Returns:
            A list of dictionaries where each dictionary contains the following keys:
                - 'value' (Any): The stored value of the metric.
                - 'step' (int): The step or index associated with the metric value.
                - 'logged_at' (datetime): A timestamp representing when the metric
                    was logged.

        Raises:
            ValueError: If the experiment with the given `experiment_id` does not exist.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value, step, logged_at FROM dynamic_metrics "
            "WHERE key = ? ORDER BY step",
            (key,),
        )
        return [
            {"value": value, "step": step, "logged_at": logged_at}
            for value, step, logged_at in cursor.fetchall()
        ]

    def get_experiment_ddl_version(self, experiment_id: str) -> int:
        db_path = self._get_experiment_db_path(experiment_id)
        conn = self.pool.get_connection(db_path)
        row = conn.execute("PRAGMA user_version").fetchone()
        return row[0] if row else 0
