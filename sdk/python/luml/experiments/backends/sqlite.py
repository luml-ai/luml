# flake8: noqa: E501
import atexit
import contextlib
import json
import sqlite3
import threading
import uuid
import weakref
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from luml.artifacts._base import DiskFile, _BaseFile
from luml.experiments.backends._base import Backend
from luml.experiments.backends.data_types import (
    Experiment,
    ExperimentData,
    ExperimentMetaData,
    Group,
    PaginationCursor,
)
from luml.experiments.backends.migration_runner import MigrationRunner
from luml.experiments.utils import guess_span_type
from luml.utils.tar import create_and_index_tar

_DDL_EXPERIMENT_CREATE_STATIC = """
    CREATE TABLE IF NOT EXISTS static_params (
        key TEXT PRIMARY KEY,
        value TEXT,
        value_type TEXT
    )
"""
_DDL_EXPERIMENT_CREATE_DYNAMIC = """
    CREATE TABLE IF NOT EXISTS dynamic_metrics (
        key TEXT,
        value REAL,
        step INTEGER,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (key, step)
    )
"""
_DDL_EXPERIMENT_CREATE_ATTACHMENTS = """
    CREATE TABLE IF NOT EXISTS attachments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        file_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_DDL_EXPERIMENT_CREATE_SPANS = """
    CREATE TABLE IF NOT EXISTS spans (
        -- OTEL identifiers
        trace_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        parent_span_id TEXT,

        -- span details
        name TEXT NOT NULL,  -- OTEL uses 'name' instead of 'operation_name'
        kind INTEGER,        -- SpanKind: 0=UNSPECIFIED, 1=INTERNAL, 2=SERVER, 3=CLIENT, 4=PRODUCER, 5=CONSUMER
        dfs_span_type INTEGER NOT NULL DEFAULT 0,  -- SpanType: 0=DEFAULT

        -- Timing
        start_time_unix_nano BIGINT NOT NULL,
        end_time_unix_nano BIGINT NOT NULL,

        -- Status
        status_code INTEGER,    -- StatusCode: 0=UNSET, 1=OK, 2=ERROR
        status_message TEXT,

        -- Span data
        attributes TEXT,       -- JSON
        events TEXT,           -- JSON
        links TEXT,            -- JSON

        trace_flags INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        PRIMARY KEY (trace_id, span_id)
    );
"""

_DDL_EXPERIMENT_CREATE_EVALS = """
    CREATE TABLE IF NOT EXISTS evals (
        id TEXT NOT NULL,
        dataset_id TEXT NOT NULL,
        inputs TEXT NOT NULL, -- JSON
        outputs TEXT, -- JSON
        refs TEXT, -- JSON
        scores TEXT, -- JSON
        metadata TEXT, -- JSON
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (dataset_id, id)
    )
"""

_DDL_EXPERIMENT_CREATE_EVAL_TRACES_BRIDGE = """
    CREATE TABLE IF NOT EXISTS eval_traces_bridge (
        id TEXT PRIMARY KEY,
        eval_dataset_id TEXT NOT NULL,
        eval_id TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


class ConnectionPool:
    def __init__(self, max_connections: int = 10) -> None:
        self.max_connections = max_connections
        self._connections: dict[str, sqlite3.Connection] = {}
        self._lock = threading.RLock()
        self._active_experiments: set[str] = set()
        atexit.register(self.close_all)

    def get_connection(self, db_path: str | Path) -> sqlite3.Connection:
        db_path = str(db_path)

        with self._lock:
            if db_path in self._connections:
                conn = self._connections[db_path]
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    self._close_connection_unsafe(db_path)

            if len(self._connections) >= self.max_connections:
                self._evict_inactive_connection()

            conn = sqlite3.Connection(db_path, check_same_thread=False)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")

            self._connections[db_path] = conn
            return conn

    def mark_experiment_active(self, experiment_id: str) -> None:
        with self._lock:
            self._active_experiments.add(experiment_id)

    def mark_experiment_inactive(self, experiment_id: str) -> None:
        with self._lock:
            self._active_experiments.discard(experiment_id)
            exp_db_pattern = f"{experiment_id}/exp.db"
            for db_path in list(self._connections.keys()):
                if db_path.endswith(exp_db_pattern):
                    self._close_connection_unsafe(db_path)

    def _evict_inactive_connection(self) -> None:
        if not self._connections:
            return

        for db_path in list(self._connections.keys()):
            if not any(
                f"{exp_id}/exp.db" in db_path for exp_id in self._active_experiments
            ) and not db_path.endswith("meta.db"):
                self._close_connection_unsafe(db_path)
                return

        inactive_paths = [p for p in self._connections if not p.endswith("meta.db")]
        if inactive_paths:
            self._close_connection_unsafe(inactive_paths[0])

    def _close_connection_unsafe(self, db_path: str) -> None:
        if db_path in self._connections:
            with contextlib.suppress(sqlite3.Error):
                self._connections[db_path].close()
            del self._connections[db_path]

    def close_connection(self, db_path: str) -> None:
        with self._lock:
            self._close_connection_unsafe(str(db_path))

    def close_all(self) -> None:
        with self._lock:
            for db_path in list(self._connections.keys()):
                self._close_connection_unsafe(db_path)

    def get_stats(self) -> dict[str, Any]:  # noqa: ANN401
        with self._lock:
            return {
                "total_connections": len(self._connections),
                "max_connections": self.max_connections,
                "active_experiments": len(self._active_experiments),
                "connections": list(self._connections.keys()),
                "active_experiment_ids": list(self._active_experiments),
            }


class SQLitePaginationMixin:
    @staticmethod
    def _items_to_dict(
        columns: list[str], rows: list[sqlite3.Row]
    ) -> list[dict[str, Any]]:
        return [dict(zip(columns, row, strict=True)) for row in rows]

    @staticmethod
    def _build_cursor_clause(
        sort_by: str,
        order: str,
        cursor_id: str | None,
        cursor_value: str | None,
    ) -> tuple[str, list[Any]]:
        if cursor_id is None:
            return "", []

        op = "<" if order == "desc" else ">"

        if cursor_value is not None:
            clause = f"""
                WHERE ({sort_by} {op} ?)
                   OR ({sort_by} = ? AND id {op} ?)
            """
            return clause, [cursor_value, cursor_value, cursor_id]

        return f"WHERE id {op} ?", [cursor_id]

    def _execute_paginated_query(
        self,
        conn: sqlite3.Connection,
        table: str,
        columns: list[str],
        limit: int,
        sort_by: str,
        order: str,
        cursor_id: str | None = None,
        cursor_value: str | None = None,
        extra_where: str = "",
        extra_params: list[Any] | None = None,
    ) -> list[sqlite3.Row]:
        where_clause, params = self._build_cursor_clause(
            sort_by,
            order,
            cursor_id,
            cursor_value,
        )

        if extra_where:
            if where_clause:
                where_clause += f" AND ({extra_where})"
            else:
                where_clause = f"WHERE {extra_where}"
            params.extend(extra_params or [])

        null_order = "LAST" if order == "desc" else "FIRST"
        cols = ", ".join(columns)
        query = f"""
            SELECT {cols}
            FROM {table}
            {where_clause}
            ORDER BY {sort_by} {order.upper()} NULLS {null_order}, id {order.upper()}
            LIMIT ?
        """
        params.append(limit + 1)

        db_cursor = conn.cursor()
        db_cursor.execute(query, params)
        return db_cursor.fetchall()

    @staticmethod
    def _build_cursor(
        items: list[dict[str, Any]],
        has_next: bool,
        sort_by: str,
    ) -> PaginationCursor | None:
        if has_next and items:
            last = items[-1]
            return PaginationCursor(id=last["id"], value=last.get(sort_by))
        return None

    @staticmethod
    def _sanitize_pagination_params(
        sort_by: str,
        order: str,
        allowed_sort_columns: set[str],
    ) -> tuple[str, str]:
        if sort_by not in allowed_sort_columns:
            sort_by = "created_at"
        order = order.lower()
        if order not in ("asc", "desc"):
            order = "desc"
        return sort_by, order


class SQLiteBackend(Backend, SQLitePaginationMixin):
    def __init__(
        self,
        config: str,
    ) -> None:
        self.base_path = Path(config)
        self.base_path.mkdir(exist_ok=True)
        self.meta_db_path = self.base_path / "meta.db"

        self.pool = ConnectionPool(10)

        self._initialize_meta_db()
        weakref.finalize(self, self._cleanup)

    def _cleanup(self) -> None:
        if hasattr(self, "pool"):
            self.pool.close_all()

    def _ensure_experiment_initialized(self, experiment_id: str) -> None:
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not initialized")

    def _get_meta_connection(self) -> sqlite3.Connection:
        return self.pool.get_connection(self.meta_db_path)

    def _get_experiment_connection(self, experiment_id: str) -> sqlite3.Connection:
        db_path = self._get_experiment_db_path(experiment_id)
        return self.pool.get_connection(db_path)

    def _get_experiment_dir(self, experiment_id: str) -> Path:
        return self.base_path / experiment_id

    def _get_experiment_db_path(self, experiment_id: str) -> Path:
        return self._get_experiment_dir(experiment_id) / "exp.db"

    def _get_attachments_dir(self, experiment_id: str) -> Path:
        return self._get_experiment_dir(experiment_id) / "attachments"

    @staticmethod
    def _convert_static_param_value(
        value: str, value_type: str
    ) -> str | int | float | bool | list | dict:
        if value_type == "json":
            return json.loads(value)
        if value_type == "int":
            return int(value)
        if value_type == "float":
            return float(value)
        if value_type == "bool":
            return value.lower() == "true"
        return value

    def _initialize_meta_db(self) -> None:
        conn = self._get_meta_connection()
        runner = MigrationRunner(conn)
        runner.migrate()

    def _initialize_experiment_db(self, experiment_id: str) -> None:
        exp_dir = self._get_experiment_dir(experiment_id)
        exp_dir.mkdir(exist_ok=True)
        attachments_dir = self._get_attachments_dir(experiment_id)
        attachments_dir.mkdir(exist_ok=True)

        db_path = self._get_experiment_db_path(experiment_id)
        conn = self.pool.get_connection(db_path)
        cursor = conn.cursor()

        cursor.execute(_DDL_EXPERIMENT_CREATE_STATIC)
        cursor.execute(_DDL_EXPERIMENT_CREATE_DYNAMIC)
        cursor.execute(_DDL_EXPERIMENT_CREATE_ATTACHMENTS)
        cursor.execute(_DDL_EXPERIMENT_CREATE_SPANS)
        cursor.execute(_DDL_EXPERIMENT_CREATE_EVALS)
        cursor.execute(_DDL_EXPERIMENT_CREATE_EVAL_TRACES_BRIDGE)
        conn.commit()

    def initialize_experiment(
        self,
        experiment_id: str,
        group: str = "Default group",
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Initializes an experiment by associating it with a group and storing its metadata in the database.

        Args:
            experiment_id: Unique identifier for the experiment.
            group: Group name to which the experiment belongs. If the group does not exist, it will
                be created. Defaults to "Default group".
            name: Optional name of the experiment. If not provided, the `experiment_id` will
                be used as the name.
            tags: Optional list of tags associated with the experiment.
        """
        if not group:
            raise ValueError(
                "Group is required. Use create_group() to create a group first."
            )
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
            INSERT OR REPLACE INTO experiments (id, name, group_id, tags)
            VALUES (?, ?, ?, ?)
        """,
            (experiment_id, name or experiment_id, group_id, tags_str),
        )

        conn.commit()

        self._initialize_experiment_db(experiment_id)
        self.pool.mark_experiment_active(experiment_id)

    def log_static(self, experiment_id: str, key: str, value: Any) -> None:  # noqa: ANN401
        """
        Logs a static parameter to the database for a given experiment.

        This method logs a static parameter with a specified key and value to the associated
        experiment. The parameter can be of type string, integer, float, boolean, or any other
        data structure that can be serialized into JSON. If a static parameter with the same key
        already exists, it will be updated.

        Args:
            experiment_id (str): The unique identifier of the experiment for which the static
                parameter is being logged.
            key (str): The key associated with the static parameter.
            value (Any): The value of the static parameter. It can be of type string, integer,
                float, boolean, or any serializable object.
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

    def log_attachment(
        self, experiment_id: str, name: str, data: bytes | str, binary: bool = False
    ) -> None:
        """
        Logs an attachment for a specific experiment by saving the data to a file and updating
        the corresponding database record.

        Args:
            experiment_id (str): The unique identifier of the experiment where the attachment
                will be logged.
            name (str): The name of the attachment file.
            data (bytes | str): The content of the attachment to be logged. This must be either
                bytes or a string.
            binary (bool): Whether the attachment data should be saved in binary mode. Defaults
                to False.

        Raises:
            ValueError: If the provided `data` is not of type `bytes` or `str`.
        """
        self._ensure_experiment_initialized(experiment_id)

        attachments_dir = self._get_attachments_dir(experiment_id)

        if not isinstance(data, bytes | str):
            raise ValueError("Attachment data must be bytes or str")

        file_path = attachments_dir / name

        with file_path.open("wb+" if binary else "w+") as f:
            f.write(data)

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO attachments (name, file_path)
            VALUES (?, ?)
        """,
            (
                name,
                str(file_path.relative_to(self._get_attachments_dir(experiment_id))),
            ),
        )

        conn.commit()

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

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        attributes_json = json.dumps(attributes) if attributes else None
        events_json = json.dumps(events) if events else None
        links_json = json.dumps(links) if links else None

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

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        inputs_json = json.dumps(inputs)
        outputs_json = json.dumps(outputs) if outputs else None
        references_json = json.dumps(references) if references else None
        scores_json = json.dumps(scores) if scores else None
        metadata_json = json.dumps(metadata) if metadata else None

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

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM evals WHERE dataset_id = ? AND id = ?",
            (eval_dataset_id, eval_id),
        )
        if not cursor.fetchone():
            raise ValueError(f"Eval {eval_id} in dataset {eval_dataset_id} not found")

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

    def get_experiment_data(self, experiment_id: str) -> ExperimentData:  # noqa: ANN401, C901
        """
        Retrieves and constructs the experiment data for a specified experiment ID from the
        corresponding database. It encompasses metadata, static parameters, dynamic metrics,
        and attachments associated with the experiment.

        Args:
            experiment_id (str): Unique identifier for the experiment.

        Returns:
            ExperimentData: An object containing all experiment data, including metadata,
            static parameters, dynamic metrics, and attachments.

        Raises:
            ValueError: If the experiment with the given experiment ID is not found.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")

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
            "SELECT name, created_at, status, group_id, tags FROM experiments WHERE id = ?",
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
            )

        return ExperimentData(
            experiment_id=experiment_id,
            metadata=metadata,
            static_params=static_params,
            dynamic_metrics=dynamic_metrics,
            attachments=attachments,
        )

    def get_attachment(self, experiment_id: str, name: str) -> Any:  # noqa: ANN401
        """
        Fetches the content of a specific attachment file associated with an experiment.

        This method retrieves the contents of an attachment file from the directory
        corresponding to a given experiment. The file is identified by its name and
        the ID of the experiment. If the experiment has not been initialized or
        the specified attachment cannot be found, appropriate errors are raised.

        Args:
            experiment_id (str): Identifier for the experiment whose attachment is
                being accessed.
            name (str): Name of the attachment file to retrieve.

        Returns:
            Any: The binary content of the specified attachment file.

        Raises:
            ValueError: If the specified attachment file is not found within the
                directory of the given experiment.
        """
        self._ensure_experiment_initialized(experiment_id)

        attachments_dir = self._get_attachments_dir(experiment_id)
        file_path = attachments_dir / name

        if not file_path.exists():
            raise ValueError(
                f"Attachment {name} not found in experiment {experiment_id}"
            )

        with file_path.open("rb") as f:
            return f.read()

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
            SELECT id, name, created_at, status, group_id, tags, static_params, dynamic_params FROM experiments
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
                )
            )
        return experiments

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
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()

        self.pool.mark_experiment_inactive(experiment_id)

        exp_dir = self._get_experiment_dir(experiment_id)
        if exp_dir.exists():
            import shutil

            shutil.rmtree(exp_dir)

    def create_group(self, name: str, description: str | None = None) -> Group:
        """
        Creates or retrieves an existing experiment group from the database.

        This method checks if a group with the specified name exists. If it exists, it retrieves
        the existing group data and returns it. Otherwise, it creates a new group in the database,
        commits the changes, and returns the newly created group.

        Args:
            name: The name of the experiment group to create or retrieve.
            description: Optional. Additional details about the group. If not provided, defaults to None.

        Returns:
            Group: An instance of the Group class containing the data for the retrieved or newly created group.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, description, created_at FROM experiment_groups WHERE name = ?",
            (name,),
        )
        existing = cursor.fetchone()
        if existing:
            return Group(
                id=existing[0],
                name=existing[1],
                description=existing[2],
                created_at=existing[3],
            )

        group_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO experiment_groups (id, name, description) VALUES (?, ?, ?)""",
            (group_id, name, description),
        )
        conn.commit()
        return Group(
            id=group_id,
            name=name,
            description=description,
            created_at=datetime.now(UTC),
        )

    def list_groups(self) -> list[Group]:  # noqa: ANN401
        """
        Retrieves a list of all experiment groups from the database and returns them as a list
        of `Group` objects. Each group contains metadata including its ID, name, description,
        and creation date.

        Returns:
            list[Group]: A list of `Group` objects representing all experiment groups in the
            database.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, created_at FROM experiment_groups"
        )
        groups = []
        for row in cursor.fetchall():
            groups.append(
                Group(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    created_at=row[3],
                )
            )
        return groups

    def list_groups_pagination(
        self,
        limit: int = 20,
        cursor_id: str | None = None,
        cursor_value: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> list[Group]:
        sort_by, order = self._sanitize_pagination_params(
            sort_by,
            order,
            {"created_at", "name"},
        )

        conn = self._get_meta_connection()
        columns = ["id", "name", "description", "created_at"]

        rows = self._execute_paginated_query(
            conn=conn,
            table="experiment_groups",
            columns=columns,
            limit=limit,
            sort_by=sort_by,
            order=order,
            cursor_id=cursor_id,
            cursor_value=cursor_value,
        )

        return [
            Group(
                id=d["id"],
                name=d["name"],
                description=d["description"],
                created_at=d["created_at"],
            )
            for d in self._items_to_dict(columns, rows)
        ]

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
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, created_at FROM experiment_groups WHERE id = ?",
            (group_id,),
        )

        if row := cursor.fetchone():
            return Group(
                id=row[0],
                name=row[1],
                description=row[2],
                created_at=row[3],
            )
        return None

    def end_experiment(self, experiment_id: str) -> None:
        """
        Finalizes the experiment by setting its status to 'completed' and saving its static
        and dynamic parameters.

        This method fetches the relevant parameters for the experiment from the database
        and updates its status and associated values in the metadata store. It ensures
        resource cleanup by marking the experiment as inactive in the connection pool.

        Args:
            experiment_id (str): The unique identifier of the experiment to be finalized.
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
            WHERE step = (SELECT MAX(step) FROM dynamic_metrics dm2 WHERE dm2.key = dm1.key)
            """
        )
        dynamic_params = dict(exp_cursor.fetchall())

        meta_conn = self._get_meta_connection()
        meta_cursor = meta_conn.cursor()
        meta_cursor.execute(
            """
            UPDATE experiments
            SET status = 'completed', static_params = ?, dynamic_params = ?
            WHERE id = ?
            """,
            (
                json.dumps(static_params) if static_params else None,
                json.dumps(dynamic_params) if dynamic_params else None,
                experiment_id,
            ),
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
