# flake8: noqa: E501
import json
import uuid
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sdk.luml.experiments.backends.sqlite import SQLiteBackend

from sdk.luml.experiments.backends._cursor import Cursor
from sdk.luml.experiments.backends.data_types import (
    ColumnField,
    ColumnType,
    EvalColumns,
    EvalRecord,
    EvalTypedColumns,
    PaginatedResponse,
)
from sdk.luml.experiments.backends.sqlite_backend._search_utils import (
    SearchEvalsUtils,
)
from sdk.luml.experiments.backends.sqlite_backend._sqlite_base import _SQLiteBase


class SQLiteEvalMixin(_SQLiteBase):
    @staticmethod
    def validate_evals_filter(search: str | None = None) -> None:
        return SearchEvalsUtils.validate_filter_string(search)

    def resolve_evals_sort_column(self, experiment_id: str, sort_by: str) -> str | None:
        """
        Resolves the json_sort_column for get_experiment_evals.

        - None        → sort_by is a standard evals column
        - "scores"    → sort_by is a score key
        - "inputs"    → sort_by is a input key
        - "outputs"   → sort_by is a output key
        - "refs"      → sort_by is a ref key
        - raises ValueError → sort_by is unknown
        """
        if sort_by in self.EVALS_STANDARD_SORT_COLUMNS:
            return None

        json_keys = self.get_experiment_eval_columns(experiment_id)

        for column, keys in vars(json_keys).items():
            if sort_by in keys:
                return column

        raise ValueError(
            f"Invalid sort_by '{sort_by}'. Must be one of "
            f"{sorted(self.EVALS_STANDARD_SORT_COLUMNS)} or "
            f"a valid scores / inputs / outputs / refs key."
        )

    def log_eval_sample(
        self,
        experiment_id: str,
        eval_id: str,
        dataset_id: str,
        inputs: dict[str, Any],  # noqa: ANN401
        outputs: dict[str, Any] | None = None,  # noqa: ANN401
        references: dict[str, Any] | None = None,  # noqa: ANN401
        scores: dict[str, Any] | None = None,  # noqa: ANN401
        metadata: dict[str, Any] | None = None,  # noqa: ANN401
    ) -> None:
        """
        Logs evaluation sample data into the database for a given experiment.

        This function inserts or updates evaluation data related to a specific experiment
        identified by its ID. Each evaluation includes information about the dataset,
        inputs, outputs, references, scores, and additional metadata. The function
        serializes the provided data into JSON format to store in the database.

        Args:
            experiment_id: Unique identifier of the experiment for which the evaluation
                is being logged.
            eval_id: Unique identifier of the evaluation sample within the experiment.
            dataset_id: Identifier of the dataset associated with the evaluation.
            inputs: A dictionary containing input data for the evaluation sample.
            outputs: A dictionary containing output data generated during the evaluation.
                It can be None if no outputs are available.
            references: A dictionary containing reference data or ground truth values
                for the evaluation. It can be None if no references are provided.
            scores: A dictionary containing evaluation scores or metrics. It can be None
                if no scores are available.
            metadata: A dictionary containing additional metadata information related to
                the evaluation sample. It can be None if no metadata is provided.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not initialized")

        self._ensure_experiment_initialized(experiment_id)
        inputs_json = json.dumps(inputs)
        outputs_json = json.dumps(outputs) if outputs else None
        references_json = json.dumps(references) if references else None
        scores_json = json.dumps(scores) if scores else None
        metadata_json = json.dumps(metadata) if metadata else None

        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO evals (
                    id, dataset_id, inputs, outputs, refs, scores, metadata, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    eval_id,
                    dataset_id,
                    inputs_json,
                    outputs_json,
                    references_json,
                    scores_json,
                    metadata_json,
                ),
            )
            conn.commit()

    def link_eval_sample_to_trace(
        self,
        experiment_id: str,
        eval_dataset_id: str,
        eval_id: str,
        trace_id: str,
    ) -> None:
        """
        Links an evaluation sample to a trace by creating or updating an entry in the
        eval_traces_bridge table. This is used to associate evaluation results with
        trace data for a given experiment context.

        Args:
            experiment_id: Identifier of the experiment containing the database.
            eval_dataset_id: Identifier of the dataset in which the evaluation resides.
            eval_id: Identifier of the evaluation to be linked.
            trace_id: Identifier of the trace to be associated with the evaluation sample.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not initialized")

        self._ensure_experiment_initialized(experiment_id)
        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM evals WHERE dataset_id = ? AND id = ?",
                (eval_dataset_id, eval_id),
            )
            if not cursor.fetchone():
                raise ValueError(
                    f"Eval {eval_id} in dataset {eval_dataset_id} not found"
                )

            cursor.execute("SELECT 1 FROM spans WHERE trace_id = ?", (trace_id,))
            if not cursor.fetchone():
                raise ValueError(f"Trace {trace_id} not found")

            bridge_id = str(uuid.uuid4())

            cursor.execute(
                """
                INSERT OR REPLACE INTO eval_traces_bridge (
                    id, eval_dataset_id, eval_id, trace_id
                ) VALUES (?, ?, ?, ?)
                """,
                (bridge_id, eval_dataset_id, eval_id, trace_id),
            )

            conn.commit()

    def get_experiment_evals(
        self,
        experiment_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: str = "created_at",
        order: Literal["asc", "desc"] = "desc",
        dataset_id: str | None = None,
        json_sort_column: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> PaginatedResponse[EvalRecord]:
        """
        Retrieve paginated eval samples for a given experiment.

        Returns eval samples with their inputs, outputs, scores, and linked trace IDs.
        Supports optional filtering by dataset_id, sorting by created_at, updated_at,
        dataset_id, or a JSON column key (via json_sort_column), and cursor-based pagination.

        Args:
            search: string to search by id.
            experiment_id: The unique identifier of the experiment.
            limit: Maximum number of evals to return. Defaults to 20.
            cursor_str: Opaque pagination cursor from a previous response.
            sort_by: Sort field or JSON key name when json_sort_column is set.
            order: Sort direction — "asc" or "desc".
            dataset_id: Filter evals to a specific dataset.
            json_sort_column: When set (e.g. "scores"), sort by json_extract(json_sort_column, '$.{sort_by}').

        Returns:
            PaginatedResponse[EvalRecord]

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_experiment_evals("exp-001", limit=2)
            PaginatedResponse(
                items=[
                    EvalRecord(
                        id="eval-001",
                        dataset_id="ds-abc",
                        inputs={"question": "What is 2+2?"},
                        outputs={"answer": "4"},
                        scores={"accuracy": 1.0},
                        metadata={"source": "test-set"},
                        created_at=datetime(2024, 6, 1, 12, 0, 0),
                        updated_at=datetime(2024, 6, 1, 12, 0, 0),
                        trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
                        annotations=AnnotationSummary(
                            feedback=[
                                FeedbackSummaryItem(
                                    name="correct",
                                    total=3,
                                    counts={"true": 2, "false": 1}
                                )
                            ],
                            expectations=[
                                ExpectationSummaryItem(
                                    name="expected_answer",
                                    total=1
                                )
                            ],
                        ),
                    ),
                ],
                cursor="eyJpZCI6ICJldmFsLTAwMSJ9",
            )
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")

        conn = self._get_experiment_connection(experiment_id)

        where_conditions: list[tuple[str, list]] = []
        use_cursor = Cursor.decode_and_validate(cursor_str, sort_by, order)

        if dataset_id:
            where_conditions.append(("dataset_id = ?", [dataset_id]))

        if search:
            where_conditions.append(
                (
                    """(id LIKE ?
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(inputs, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(outputs, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(refs, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(scores, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(metadata, '{}')) WHERE type = 'text' AND value LIKE ?))""",
                    [f"%{search}%"] * 6,
                )
            )

        for f in filters or []:
            filter_where, filter_params = SearchEvalsUtils.to_sql(f)
            if filter_where:
                where_conditions.append((filter_where, filter_params))

        columns = [
            "id",
            "dataset_id",
            "inputs",
            "outputs",
            "refs",
            "scores",
            "metadata",
            "created_at",
            "updated_at",
        ]
        rows = self._execute_paginated_query(
            conn=conn,
            table="evals",
            columns=columns,
            limit=limit,
            sort_by=sort_by,
            order=order,
            cursor_id=use_cursor.id if use_cursor else None,
            cursor_value=use_cursor.value if use_cursor else None,
            where=where_conditions or None,
            allowed_sort_columns=self.EVALS_STANDARD_SORT_COLUMNS,
            json_sort_column=json_sort_column,
            id_column="id",
        )

        has_more = len(rows) > limit
        rows = rows[:limit]

        if not rows:
            return PaginatedResponse(items=[], cursor=None)

        evals = [
            EvalRecord(
                id=row[0],
                dataset_id=row[1],
                inputs=json.loads(row[2]) if row[2] else {},
                outputs=json.loads(row[3]) if row[3] else None,
                refs=json.loads(row[4]) if row[4] else None,
                scores=json.loads(row[5]) if row[5] else None,
                metadata=json.loads(row[6]) if row[6] else None,
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]
        eval_ids = [e.id for e in evals]

        traces_by_eval = self._fetch_bridge_ids(
            conn, "eval_id", "trace_id", [e.id for e in evals]
        )
        for e in evals:
            e.trace_ids = traces_by_eval.get(e.id, [])

        summaries = self.get_evals_annotation_summaries(experiment_id, eval_ids)

        for e in evals:
            e.annotations = summaries.get(e.id)

        cursor: str | None = None
        if has_more:
            last = evals[-1]
            last_sort_val = self._extract_cursor_value(
                rows[-1], columns, sort_by, json_sort_column
            )
            cursor = Cursor(
                id=last.id,
                value=last_sort_val,
                sort_by=sort_by,
                order=order,
            ).encode()

        return PaginatedResponse(items=evals, cursor=cursor)

    def get_experiment_evals_all(
        self,
        experiment_id: str,
        sort_by: str = "created_at",
        order: Literal["asc", "desc"] = "desc",
        dataset_id: str | None = None,
        json_sort_column: str | None = None,
        search: str | None = None,
        filters: list[str] | None = None,
    ) -> list[EvalRecord]:
        """
        Retrieve all eval records for a given experiment.

        Returns evals with their inputs, outputs, scores, and linked trace IDs.
        Supports optional filtering by dataset_id, sorting by created_at, updated_at,
        dataset_id, or a JSON column key (via json_sort_column).

        Args:
            experiment_id: The unique identifier of the experiment.
            sort_by: Sort field or JSON key name when json_sort_column is set.
            order: Sort direction — "asc" or "desc".
            dataset_id: Filter evals to a specific dataset.
            json_sort_column: When set (e.g. "scores"), sort by json_extract(json_sort_column, '$.{sort_by}').
            search: string to search by name or tag.

        Returns:
            list[EvalRecord]

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_experiment_evals_all("exp-001")
            [
                EvalRecord(
                    id="eval-001",
                    dataset_id="ds-abc",
                    inputs={"question": "What is 2+2?"},
                    outputs={"answer": "4"},
                    scores={"accuracy": 1.0},
                    metadata={"source": "test-set"},
                    created_at=datetime(2024, 6, 1, 12, 0, 0),
                    updated_at=datetime(2024, 6, 1, 12, 0, 0),
                    trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
                    annotations=AnnotationSummary(
                        feedback=[
                            FeedbackSummaryItem(
                                name="correct",
                                total=3,
                                counts={"true": 2, "false": 1}
                            )
                        ],
                        expectations=[
                            ExpectationSummaryItem(
                                name="expected_answer",
                                total=1
                            )
                        ],
                    ),
                ),
            ]
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")

        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)

        where_clauses: list[str] = []
        params: list[Any] = []

        if dataset_id:
            where_clauses.append("dataset_id = ?")
            params.append(dataset_id)
        if search:
            where_clauses.append(
                """(id LIKE ?
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(inputs, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(outputs, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(refs, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(scores, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(metadata, '{}')) WHERE type = 'text' AND value LIKE ?))"""
            )
            params.extend([f"%{search}%"] * 6)

        for f in filters or []:
            filter_where, filter_params = SearchEvalsUtils.to_sql(f)
            if filter_where:
                where_clauses.append(filter_where)
                params.extend(filter_params)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sort_expr = self._build_sort_expr(
            sort_by, json_sort_column, self.EVALS_STANDARD_SORT_COLUMNS
        )
        null_order = "LAST" if order == "desc" else "FIRST"

        rows = conn.execute(
            f"""
            SELECT id, dataset_id, inputs, outputs, refs, scores, metadata, created_at, updated_at
            FROM evals
            {where_sql}
            ORDER BY {sort_expr} {order.upper()} NULLS {null_order}, id {order.upper()}
            """,
            params,
        ).fetchall()

        if not rows:
            return []

        evals = [
            EvalRecord(
                id=row[0],
                dataset_id=row[1],
                inputs=json.loads(row[2]) if row[2] else {},
                outputs=json.loads(row[3]) if row[3] else None,
                refs=json.loads(row[4]) if row[4] else None,
                scores=json.loads(row[5]) if row[5] else None,
                metadata=json.loads(row[6]) if row[6] else None,
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]
        eval_ids = [e.id for e in evals]

        traces_by_eval = self._fetch_bridge_ids(conn, "eval_id", "trace_id", eval_ids)
        for e in evals:
            e.trace_ids = traces_by_eval.get(e.id, [])

        summaries = self.get_evals_annotation_summaries(experiment_id, eval_ids)
        for e in evals:
            e.annotations = summaries.get(e.id)

        return evals

    def get_eval(self, experiment_id: str, eval_id: str) -> EvalRecord | None:
        """
        Retrieves an evaluation record associated with a given experiment and evaluation ID

        Args:
            experiment_id (str): the experiment id
            eval_id (str): id of the specific evaluation to retrieve

        Returns:
            EvalRecord | None: Returns `None` if no such record exists.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_eval("experiment_id", "eval_id")
            EvalRecord(
                id="eval-001",
                dataset_id="ds-abc",
                inputs={"question": "What is 2+2?"},
                outputs={"answer": "4"},
                scores={"accuracy": 1.0},
                metadata={"source": "test-set"},
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                updated_at=datetime(2024, 6, 1, 12, 0, 0),
                trace_ids=["4bf92f3577b34da6a3ce929d0e0e4736"],
                annotations=None
            )
        """
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)

        row = conn.execute(
            """
            SELECT id, dataset_id, inputs, outputs, refs, scores, metadata, created_at, updated_at
            FROM evals WHERE id = ?
            """,
            (eval_id,),
        ).fetchone()

        if not row:
            return None

        eval_item = EvalRecord(
            id=row[0],
            dataset_id=row[1],
            inputs=json.loads(row[2]) if row[2] else {},
            outputs=json.loads(row[3]) if row[3] else None,
            refs=json.loads(row[4]) if row[4] else None,
            scores=json.loads(row[5]) if row[5] else None,
            metadata=json.loads(row[6]) if row[6] else None,
            created_at=row[7],
            updated_at=row[8],
        )

        traces_by_eval = self._fetch_bridge_ids(conn, "eval_id", "trace_id", [eval_id])
        eval_item.trace_ids = traces_by_eval.get(eval_id, [])

        return eval_item

    def get_experiment_eval_columns(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> EvalColumns:
        """
        Returns all evals for the experiment with their inputs, outputs, refs, and scores.

        Args:
            dataset_id: dataset_id for filtering
            experiment_id: The unique identifier of the experiment.

        Returns:
            list[EvalColumns]: All evals with scoring-relevant fields.

        """
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)

        def _keys(col: str) -> list[str]:
            cur = conn.cursor()
            if dataset_id is not None:
                cur.execute(
                    f"""
                    SELECT DISTINCT je.key
                    FROM evals, json_each(evals.{col}) AS je
                    WHERE evals.{col} IS NOT NULL AND evals.dataset_id = ?
                    ORDER BY je.key
                    """,
                    (dataset_id,),
                )
            else:
                cur.execute(
                    f"""
                    SELECT DISTINCT je.key
                    FROM evals, json_each(evals.{col}) AS je
                    WHERE evals.{col} IS NOT NULL
                    ORDER BY je.key
                    """
                )
            return [row[0] for row in cur.fetchall()]

        return EvalColumns(
            inputs=_keys("inputs"),
            outputs=_keys("outputs"),
            refs=_keys("refs"),
            scores=_keys("scores"),
            metadata=_keys("metadata"),
        )

    def get_experiment_eval_typed_columns(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> EvalTypedColumns:
        """Like get_experiment_eval_columns but also returns the SQLite type for each key."""
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)

        def _fields(col: str) -> list[ColumnField]:
            cur = conn.cursor()
            if dataset_id is not None:
                cur.execute(
                    f"""
                    SELECT je.key, je.type
                    FROM evals, json_each(evals.{col}) AS je
                    WHERE evals.{col} IS NOT NULL AND evals.dataset_id = ?
                    GROUP BY je.key
                    ORDER BY je.key
                    """,
                    (dataset_id,),
                )
            else:
                cur.execute(
                    f"""
                    SELECT je.key, je.type
                    FROM evals, json_each(evals.{col}) AS je
                    WHERE evals.{col} IS NOT NULL
                    GROUP BY je.key
                    ORDER BY je.key
                    """
                )
            return [
                ColumnField(
                    name=row[0],
                    type=self._SQLITE_TYPE_MAP.get(row[1], ColumnType.UNKNOWN),
                )
                for row in cur.fetchall()
            ]

        def _annotation_fields(kind: str) -> list[ColumnField]:
            if not self._has_annotation_tables(experiment_id):
                return []
            cur = conn.cursor()
            if dataset_id is not None:
                cur.execute(
                    """
                    SELECT name, value_type
                    FROM eval_annotations
                    WHERE annotation_kind = ? AND dataset_id = ?
                    GROUP BY name
                    ORDER BY name
                    """,
                    (kind, dataset_id),
                )
            else:
                cur.execute(
                    """
                    SELECT name, value_type
                    FROM eval_annotations
                    WHERE annotation_kind = ?
                    GROUP BY name
                    ORDER BY name
                    """,
                    (kind,),
                )
            return [
                ColumnField(
                    name=row[0],
                    type=self._ANNOTATION_VALUE_TYPE_MAP.get(
                        row[1], ColumnType.UNKNOWN
                    ),
                )
                for row in cur.fetchall()
            ]

        return EvalTypedColumns(
            inputs=_fields("inputs"),
            outputs=_fields("outputs"),
            refs=_fields("refs"),
            scores=_fields("scores"),
            metadata=_fields("metadata"),
            annotations_feedback=_annotation_fields("feedback"),
            annotations_expectations=_annotation_fields("expectation"),
        )

    def get_experiment_eval_dataset_ids(self, experiment_id: str) -> list[str]:
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT dataset_id FROM evals ORDER BY dataset_id")
        return [row[0] for row in cur.fetchall()]

    def get_evals_average_scores(
        self, experiment_id: str, dataset_id: str | None = None
    ) -> dict[str, float]:
        """
        Calculates the average scores for evaluations from a specified experiment and optionally
        filters them by a specific dataset.

        Args:
            experiment_id (str): The unique identifier of the experiment from which to fetch
                evaluation data.
            dataset_id (str | None, optional): The unique identifier of the dataset to filter
                evaluations. If not provided, all datasets within the experiment will be considered.

        Returns:
            dict[str, float]: A dictionary where the keys are evaluation metric names and the values
                are their corresponding average scores.
        """
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cur = conn.cursor()
        if dataset_id is not None:
            cur.execute(
                """
                SELECT je.key, AVG(CAST(je.value AS REAL))
                FROM evals, json_each(evals.scores) AS je
                WHERE evals.scores IS NOT NULL AND evals.dataset_id = ?
                GROUP BY je.key
                """,
                (dataset_id,),
            )
        else:
            cur.execute(
                """
                SELECT je.key, AVG(CAST(je.value AS REAL))
                FROM evals, json_each(evals.scores) AS je
                WHERE evals.scores IS NOT NULL
                GROUP BY je.key
                """
            )
        return {row[0]: row[1] for row in cur.fetchall()}
