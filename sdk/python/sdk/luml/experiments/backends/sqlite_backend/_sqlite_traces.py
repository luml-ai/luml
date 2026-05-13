# flake8: noqa: E501
import json
import sqlite3
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from luml.experiments.backends.sqlite import SQLiteBackend  # noqa: F401

from luml.experiments.backends._cursor import Cursor
from luml.experiments.backends.data_types import (
    ColumnField,
    ColumnType,
    PaginatedResponse,
    SpanRecord,
    TraceColumns,
    TraceDetails,
    TraceRecord,
    TraceState,
    TraceTypedColumns,
)
from luml.experiments.backends.sqlite_backend._search_utils import (
    SearchTracesUtils,
)
from luml.experiments.backends.sqlite_backend._sqlite_base import _SQLiteBase
from luml.experiments.utils import guess_span_type


class SQLiteTraceMixin(_SQLiteBase):
    @staticmethod
    def _fetch_bridge_ids(
        conn: sqlite3.Connection,
        key_column: str,
        value_column: str,
        ids: list[str],
    ) -> dict[str, list[str]]:
        if not ids:
            return {}
        result: dict[str, list[str]] = {}
        batch_size = 900
        cur = conn.cursor()
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            placeholders = ", ".join("?" for _ in batch)
            cur.execute(
                f"SELECT {key_column}, {value_column} FROM eval_traces_bridge"
                f" WHERE {key_column} IN ({placeholders})",
                batch,
            )
            for key, value in cur.fetchall():
                result.setdefault(key, []).append(value)
        return result

    @staticmethod
    def validate_traces_filter(search: str | None = None) -> None:
        return SearchTracesUtils.validate_filter_string(search)

    def log_span(
        self,
        experiment_id: str,
        trace_id: str,
        span_id: str,
        name: str,
        start_time_unix_nano: int,
        end_time_unix_nano: int,
        parent_span_id: str | None = None,
        kind: int = 0,
        status_code: int = 0,
        status_message: str | None = None,
        attributes: dict[str, Any] | None = None,  # noqa: ANN401
        events: list[dict[str, Any]] | None = None,  # noqa: ANN401
        links: list[dict[str, Any]] | None = None,  # noqa: ANN401
        trace_flags: int = 0,
    ) -> None:
        """
        Logs a span into the database for a specific experiment. This function inserts or replaces
        a span record in the `spans` table associated with a given experiment. It allows the user
        to register spans with detailed metadata including trace IDs, span attributes, events,
        links, timestamps, and status information.

        Args:
            experiment_id (str): Identifier for the experiment to which the span belongs.
            trace_id (str): Unique identifier for the trace.
            span_id (str): Unique identifier for the span.
            name (str): Name associated with the span.
            start_time_unix_nano (int): Span start time in nanoseconds since Unix epoch.
            end_time_unix_nano (int): Span end time in nanoseconds since Unix epoch.
            parent_span_id (str | None): Identifier for the parent span, or None if root span.
            kind (int): Type of the span (e.g., internal, server, client).
            status_code (int): Status code of the span (e.g., OK, ERROR).
            status_message (str | None): Human-readable description of the span's status,
                                         or None if not provided.
            attributes (dict[str, Any] | None): Arbitrary span attributes, or None if not provided.
            events (list[dict[str, Any]] | None): List of event dictionaries associated with the span,
                                                  or None if no events are present.
            links (list[dict[str, Any]] | None): List of link dictionaries associated with the span,
                                                 or None for no links.
            trace_flags (int): Flags providing additional trace information.

        Raises:
            ValueError: If the specified experiment does not exist, or has not been initialized.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not initialized")

        self._ensure_experiment_initialized(experiment_id)
        attributes_json = json.dumps(attributes) if attributes else None
        events_json = json.dumps(events) if events else None
        links_json = json.dumps(links) if links else None

        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO spans (
                    trace_id, span_id, parent_span_id, name, kind,
                    start_time_unix_nano, end_time_unix_nano,
                    status_code, status_message,
                    attributes, events, links, trace_flags, dfs_span_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    span_id,
                    parent_span_id,
                    name,
                    kind,
                    start_time_unix_nano,
                    end_time_unix_nano,
                    status_code,
                    status_message,
                    attributes_json,
                    events_json,
                    links_json,
                    trace_flags,
                    guess_span_type(attributes).value if attributes else 0,
                ),
            )
            conn.commit()

    def get_experiment_traces(
        self,
        experiment_id: str,
        limit: int = 20,
        cursor_str: str | None = None,
        sort_by: Literal[
            "execution_time", "span_count", "created_at"
        ] = "execution_time",
        order: Literal["asc", "desc"] = "desc",
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> PaginatedResponse[TraceRecord]:
        """
        Retrieve paginated trace summaries for a given experiment.

        Returns an aggregated summary per trace: trace_id, execution_time
        (MAX(end) - MIN(start) across all spans in seconds), span_count,
        created_at, state, and linked eval IDs. Supports filtering by trace_id
        substring and state, sorting by execution_time, span_count or created_at,
        and cursor-based pagination.

        Args:
            experiment_id: The unique identifier of the experiment.
            limit: Maximum number of summaries to return. Defaults to 20.
            cursor_str: Opaque pagination cursor from a previous response.
            sort_by: Sort field — "execution_time", "span_count", or "created_at".
            order: Sort direction — "asc" or "desc".
            search: Substring to filter trace_id (LIKE %...%).
            states: Filter by one or more TraceState values.

        Returns:
            PaginatedResponse[TraceRecord]

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_experiment_traces(
            >>>    "exp-001", limit=2, sort_by="execution_time", order="desc"
            >>> )
            PaginatedResponse(
                items=[
                    TraceRecord(
                        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
                        execution_time=15.442,
                        span_count=6,
                        created_at=datetime(2024, 6, 1, 12, 0, 1),
                        state=TraceState.OK,
                        evals=["eval-001", "eval-002"],
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
                cursor="eyJ0cmFjZV9pZCI6ICJhM2NlOTI5ZC4uLiJ9",
            )
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")

        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)

        subquery = """(
            SELECT
                trace_id,
                (MAX(end_time_unix_nano) - MIN(start_time_unix_nano)) AS execution_time,
                COUNT(*) AS span_count,
                MIN(created_at) AS created_at,
                CASE
                    WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) IS NULL THEN 3
                    WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 2 THEN 2
                    WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 1 THEN 1
                    ELSE 0
                END AS state
            FROM spans
            GROUP BY trace_id
        )"""

        where_conditions: list[tuple[str, list]] = []

        if search:
            where_conditions.append(
                (
                    """trace_id IN (
                    SELECT DISTINCT trace_id FROM spans
                    WHERE trace_id LIKE ?
                       OR COALESCE(status_message, '') LIKE ?
                       OR EXISTS (SELECT 1 FROM json_each(COALESCE(attributes, '{}')) WHERE type = 'text' AND value LIKE ?)
                       OR COALESCE(events, '') LIKE ?
                       OR COALESCE(links, '') LIKE ?
                )""",
                    [f"%{search}%"] * 5,
                )
            )

        for f in filters or []:
            filter_where, filter_params = SearchTracesUtils.to_sql(f)
            if filter_where:
                where_conditions.append((filter_where, filter_params))

        if states:
            where_conditions.append(
                (
                    f"state IN ({', '.join('?' for _ in states)})",
                    [s.value for s in states],
                )
            )
        use_cursor = Cursor.decode_and_validate(cursor_str, sort_by, order)

        columns = ["trace_id", "execution_time", "span_count", "created_at", "state"]
        rows = self._execute_paginated_query(
            conn=conn,
            table=subquery,
            columns=columns,
            limit=limit,
            sort_by=sort_by,
            order=order,
            cursor_id=use_cursor.id if use_cursor else None,
            cursor_value=use_cursor.value if use_cursor else None,
            where=where_conditions or None,
            allowed_sort_columns={"execution_time", "span_count", "created_at"},
            id_column="trace_id",
        )

        has_more = len(rows) > limit
        rows = rows[:limit]

        if not rows:
            return PaginatedResponse(items=[], cursor=None)

        items = [
            TraceRecord(
                trace_id=row[0],
                execution_time=row[1],
                span_count=row[2],
                created_at=row[3],
                state=TraceState(row[4]),
            )
            for row in rows
        ]

        evals_by_trace = self._fetch_bridge_ids(
            conn, "trace_id", "eval_id", [item.trace_id for item in items]
        )
        for item in items:
            item.evals = evals_by_trace.get(item.trace_id, [])

        cursor: str | None = None
        if has_more:
            cursor = Cursor(
                id=items[-1].trace_id,
                value=self._extract_cursor_value(rows[-1], columns, sort_by),
                sort_by=sort_by,
                order=order,
            ).encode()

        return PaginatedResponse(items=items, cursor=cursor)

    def get_experiment_traces_all(
        self,
        experiment_id: str,
        sort_by: str = "execution_time",
        order: Literal["asc", "desc"] = "desc",
        search: str | None = None,
        filters: list[str] | None = None,
        states: list[TraceState] | None = None,
    ) -> list[TraceRecord]:
        """
        Retrieve paginated trace summaries for a given experiment.

        Returns an aggregated summary per trace: trace_id, execution_time
        (MAX(end) - MIN(start) across all spans in seconds), span_count,
        created_at, state, and linked eval IDs. Supports filtering by trace_id
        substring and state, sorting by execution_time, span_count or created_at,
        and cursor-based pagination.

        Args:
            experiment_id: The unique identifier of the experiment.
            sort_by: Sort field — "execution_time", "span_count", or "created_at".
            order: Sort direction — "asc" or "desc".
            search: Substring to filter trace_id (LIKE %...%).
            states: Filter by one or more TraceState values.

        Returns:
            PaginatedResponse[TraceRecord]

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_experiment_traces(
            >>>    "exp-001", sort_by="execution_time", order="desc"
            >>> )
            [
                TraceRecord(
                    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
                    execution_time=15.442,
                    span_count=6,
                    created_at=datetime(2024, 6, 1, 12, 0, 1),
                    state=TraceState.OK,
                    evals=["eval-001", "eval-002"],
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

        subquery = """(
            SELECT
                trace_id,
                (MAX(end_time_unix_nano) - MIN(start_time_unix_nano)) AS execution_time,
                COUNT(*) AS span_count,
                MIN(created_at) AS created_at,
                CASE
                    WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) IS NULL THEN 3
                    WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 2 THEN 2
                    WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 1 THEN 1
                    ELSE 0
                END AS state
            FROM spans
            GROUP BY trace_id
        )"""

        where_clauses: list[str] = []
        params: list[Any] = []
        if search:
            where_clauses.append("""trace_id IN (
                SELECT DISTINCT trace_id FROM spans
                WHERE trace_id LIKE ?
                   OR COALESCE(status_message, '') LIKE ?
                   OR EXISTS (SELECT 1 FROM json_each(COALESCE(attributes, '{}')) WHERE type = 'text' AND value LIKE ?)
                   OR COALESCE(events, '') LIKE ?
                   OR COALESCE(links, '') LIKE ?
            )""")
            params.extend([f"%{search}%"] * 5)
        for f in filters or []:
            filter_where, filter_params = SearchTracesUtils.to_sql(f)
            if filter_where:
                where_clauses.append(filter_where)
                params.extend(filter_params)
        if states:
            where_clauses.append(f"state IN ({', '.join('?' for _ in states)})")
            params.extend(s.value for s in states)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sort_expr = self._build_sort_expr(
            sort_by, None, {"execution_time", "span_count", "created_at"}
        )
        null_order = "LAST" if order == "desc" else "FIRST"

        rows = conn.execute(
            f"""
            SELECT trace_id, execution_time, span_count, created_at, state
            FROM {subquery}
            {where_sql}
            ORDER BY {sort_expr} {order.upper()} NULLS {null_order}, trace_id {order.upper()}
            """,
            params,
        ).fetchall()

        if not rows:
            return []

        items = [
            TraceRecord(
                trace_id=row[0],
                execution_time=row[1],
                span_count=row[2],
                created_at=row[3],
                state=TraceState(row[4]),
            )
            for row in rows
        ]

        evals_by_trace = self._fetch_bridge_ids(
            conn, "trace_id", "eval_id", [item.trace_id for item in items]
        )
        for item in items:
            item.evals = evals_by_trace.get(item.trace_id, [])

        trace_ids = [item.trace_id for item in items]
        summaries = self.get_traces_annotation_summaries(experiment_id, trace_ids)
        for item in items:
            item.annotations = summaries.get(item.trace_id)

        return items

    def get_trace(self, experiment_id: str, trace_id: str) -> TraceDetails | None:
        """
        Retrieves trace details for a given trace ID within an experiment.

        This method queries the database associated with the specified experiment ID
        to fetch detailed information about the trace, including span records and
        their associated metadata. If the trace ID does not exist within the database,
        the method returns None. Errors are raised if the experiment's database is not
        found.

        Args:
            experiment_id (str): The unique identifier of the experiment whose trace
                details are being retrieved.
            trace_id (str): The unique identifier of the trace within the experiment.

        Returns:
            TraceDetails | None: A TraceDetails object containing the trace ID and
            its associated spans if the trace is found; otherwise, None.

        Raises:
            ValueError: If the specified experiment ID does not have an associated
            database or the database cannot be found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_trace("exp-001", "4bf92f3577b34da6a3ce929d0e0e4736")
            TraceDetails(
                trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
                spans=[
                    SpanRecord(
                        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
                        span_id="00f067aa0ba902b7",
                        parent_span_id=None,
                        name="agent.run",
                        kind=1,
                        dfs_span_type=2,
                        start_time_unix_nano=1717200000000000000,
                        end_time_unix_nano=1717200015442000000,
                        status_code=1,
                        status_message=None,
                        attributes={"llm.model": "gpt-4o", "llm.token_count": 512},
                        events=None,
                        links=None,
                        trace_flags=1,
                    )
                ]
            )
        """
        self._ensure_experiment_initialized(experiment_id)
        has_annotations = self._has_annotation_tables(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cur = conn.cursor()
        if has_annotations:
            cur.execute(
                """
                SELECT s.trace_id, s.span_id, s.parent_span_id, s.name, s.kind,
                       s.dfs_span_type, s.start_time_unix_nano, s.end_time_unix_nano,
                       s.status_code, s.status_message, s.attributes, s.events, s.links,
                       s.trace_flags, COUNT(sa.id) AS annotation_count
                FROM spans s
                LEFT JOIN span_annotations sa
                    ON s.trace_id = sa.trace_id AND s.span_id = sa.span_id
                WHERE s.trace_id = ?
                GROUP BY s.trace_id, s.span_id
                ORDER BY s.start_time_unix_nano
                """,
                (trace_id,),
            )
        else:
            cur.execute(
                """
                SELECT trace_id, span_id, parent_span_id, name, kind,
                       dfs_span_type, start_time_unix_nano, end_time_unix_nano,
                       status_code, status_message, attributes, events, links,
                       trace_flags, 0 AS annotation_count
                FROM spans
                WHERE trace_id = ?
                ORDER BY start_time_unix_nano
                """,
                (trace_id,),
            )
        rows = cur.fetchall()
        if not rows:
            return None

        spans = [
            SpanRecord(
                trace_id=row[0],
                span_id=row[1],
                parent_span_id=row[2],
                name=row[3],
                kind=row[4],
                dfs_span_type=row[5],
                start_time_unix_nano=row[6],
                end_time_unix_nano=row[7],
                status_code=row[8],
                status_message=row[9],
                attributes=json.loads(row[10]) if row[10] else None,
                events=json.loads(row[11]) if row[11] else None,
                links=json.loads(row[12]) if row[12] else None,
                trace_flags=row[13],
                annotation_count=row[14],
            )
            for row in rows
        ]
        return TraceDetails(trace_id=trace_id, spans=spans)

    def get_experiment_trace_columns(self, experiment_id: str) -> TraceColumns:
        """Return distinct attribute keys from all spans in an experiment."""
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cur = conn.execute(
            """
            SELECT DISTINCT je.key
            FROM spans, json_each(spans.attributes) AS je
            WHERE spans.attributes IS NOT NULL
            ORDER BY je.key
            """
        )
        return TraceColumns(attributes=[row[0] for row in cur.fetchall()])

    def get_experiment_trace_typed_columns(
        self, experiment_id: str
    ) -> TraceTypedColumns:
        """Like get_experiment_trace_columns but also returns the type for each key."""
        self._ensure_experiment_initialized(experiment_id)
        conn = self._get_experiment_connection(experiment_id)
        cur = conn.execute(
            """
            SELECT je.key, je.type
            FROM spans, json_each(spans.attributes) AS je
            WHERE spans.attributes IS NOT NULL
            GROUP BY je.key
            ORDER BY je.key
            """
        )
        attributes = [
            ColumnField(
                name=row[0],
                type=self._SQLITE_TYPE_MAP.get(row[1], ColumnType.UNKNOWN),
            )
            for row in cur.fetchall()
        ]

        def _annotation_fields(kind: str) -> list[ColumnField]:
            if not self._has_annotation_tables(experiment_id):
                return []
            rows = conn.execute(
                """
                SELECT name, value_type
                FROM span_annotations
                WHERE annotation_kind = ?
                GROUP BY name
                ORDER BY name
                """,
                (kind,),
            ).fetchall()
            return [
                ColumnField(
                    name=row[0],
                    type=self._ANNOTATION_VALUE_TYPE_MAP.get(
                        row[1], ColumnType.UNKNOWN
                    ),
                )
                for row in rows
            ]

        return TraceTypedColumns(
            attributes=attributes,
            annotations_feedback=_annotation_fields("feedback"),
            annotations_expectations=_annotation_fields("expectation"),
        )
