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
from typing import Any, Literal

from luml.artifacts._base import DiskFile, _BaseFile
from luml.experiments.backends._base import Backend
from luml.experiments.backends._cursor import Cursor
from luml.experiments.backends._search_utils import SearchExperimentsUtils
from luml.experiments.backends._sqlite_experiment_ddl import (
    _DDL_EXPERIMENT_CREATE_ATTACHMENTS,
    _DDL_EXPERIMENT_CREATE_DYNAMIC,
    _DDL_EXPERIMENT_CREATE_EVAL_ANNOTATIONS,
    _DDL_EXPERIMENT_CREATE_EVAL_TRACES_BRIDGE,
    _DDL_EXPERIMENT_CREATE_EVALS,
    _DDL_EXPERIMENT_CREATE_SPAN_ANNOTATIONS,
    _DDL_EXPERIMENT_CREATE_SPANS,
    _DDL_EXPERIMENT_CREATE_STATIC,
    EXPERIMENT_DDL_VERSION,
)
from luml.experiments.backends._sqlite_pagination_mixin import SQLitePaginationMixin
from luml.experiments.backends.data_types import (
    AnnotationKind,
    AnnotationRecord,
    AnnotationSummary,
    AnnotationValueType,
    EvalColumns,
    EvalRecord,
    ExpectationSummaryItem,
    Experiment,
    ExperimentData,
    ExperimentMetaData,
    FeedbackSummaryItem,
    Group,
    Model,
    PaginatedResponse,
    SpanRecord,
    TraceDetails,
    TraceRecord,
    TraceState,
)
from luml.experiments.backends.migration_runner import MigrationRunner
from luml.experiments.utils import guess_span_type
from luml.utils.tar import create_and_index_tar


class ConnectionPool:
    def __init__(self, max_connections: int = 10) -> None:
        self.max_connections = max_connections
        self._connections: dict[str, sqlite3.Connection] = {}
        self._write_locks: dict[str, threading.Lock] = {}
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
            self._write_locks[db_path] = threading.Lock()
            return conn

    def get_write_lock(self, db_path: str | Path) -> threading.Lock:
        db_path = str(db_path)
        with self._lock:
            if db_path not in self._write_locks:
                self._write_locks[db_path] = threading.Lock()
            return self._write_locks[db_path]

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
            self._write_locks.pop(db_path, None)

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


class SQLiteBackend(Backend, SQLitePaginationMixin):
    _STANDARD_EXPERIMENT_SORT_COLUMNS = {
        "name",
        "created_at",
        "status",
        "tags",
        "duration",
    }
    EVALS_STANDARD_SORT_COLUMNS: frozenset[str] = frozenset(
        {"created_at", "updated_at", "dataset_id"}
    )
    _EXPERIMENT_COLUMNS = [
        "id",
        "group_id",
        "name",
        "created_at",
        "status",
        "tags",
        "duration",
        "description",
        "static_params",
        "dynamic_params",
    ]

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

    def _get_experiment_write_lock(self, experiment_id: str) -> threading.Lock:
        db_path = self._get_experiment_db_path(experiment_id)
        return self.pool.get_write_lock(db_path)

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
        cursor.execute(_DDL_EXPERIMENT_CREATE_EVAL_ANNOTATIONS)
        cursor.execute(_DDL_EXPERIMENT_CREATE_SPAN_ANNOTATIONS)
        cursor.execute(f"PRAGMA user_version = {EXPERIMENT_DDL_VERSION}")
        conn.commit()

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Model:
        return Model(
            id=row[0],
            name=row[1],
            created_at=row[2],
            tags=json.loads(row[3]) if row[3] else [],
            path=row[4],
            size=row[5],
            experiment_id=row[6],
        )

    def _fetch_model(self, cursor: sqlite3.Cursor, model_id: str) -> Model | None:
        cursor.execute(
            "SELECT id, name, created_at, tags, path, size, experiment_id FROM models WHERE id = ?",
            (model_id,),
        )
        row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def initialize_experiment(
        self,
        experiment_id: str,
        group: str = "default",
        name: str | None = None,
        tags: list[str] | None = None,
        description: str | None = None,
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
            description: Optional description of the experiment.
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
            INSERT OR REPLACE INTO experiments (id, name, group_id, tags, description)
            VALUES (?, ?, ?, ?, ?)
        """,
            (experiment_id, name or experiment_id, group_id, tags_str, description),
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
        file_path.parent.mkdir(parents=True, exist_ok=True)

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

        This method queries the database to retrieve information about a specific experiment
        based on its unique identifier. If no experiment is found, the method returns None.

        Args:
            experiment_id (str): The unique identifier of the experiment to retrieve.

        Returns:
            Experiment | None: An instance of the `Experiment` class containing the details of
            the experiment if found, or None if no matching record exists.
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
        Updates an existing experiment record in the database. Fields such as name, description,
        and tags can be updated selectively. If no fields are updated, the function retrieves
        the current experiment details.

        Args:
            experiment_id: Unique identifier of the experiment to update.
            name: Optional new name for the experiment.
            description: Optional new description for the experiment.
            tags: Optional list of new tags associated with the experiment.

        Returns:
            Experiment: Updated experiment object if the update is successful or the record is retrieved.
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
                "SELECT id, name, created_at, status, tags, duration, description, group_id "
                "FROM experiments WHERE id = ?",
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
            "SELECT id, name, created_at, status, tags, duration, description, group_id "
            "FROM experiments WHERE id = ?",
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
        Deletes a group from the experiment groups database.

        This method removes the entry corresponding to the given group ID
        from the 'experiment_groups' table in the database.

        Args:
            group_id (str): The unique identifier of the group to be deleted.

        Returns:
            None
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
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

    def log_model(
        self,
        experiment_id: str,
        model_path: str,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[Model, str]:
        """
        Logs a machine learning model to the specified experiment by storing its metadata and
        copying the model file to the appropriate storage location.

        Args:
            experiment_id (str): The unique identifier of the experiment to which the model
                is logged.
            model_path (str): The file path of the model to be logged.
            name (str | None, optional): The name of the model. If not provided, the stem of
                the model file name is used.
            tags (list[str] | None, optional): A list of tags associated with the model to
                provide metadata for organizational or informational purposes.

        Returns:
            tuple[Model, str]: A tuple containing the `Model` object representing the logged
                model's metadata and the absolute destination path of the copied model file.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> model, dest_path = backend.log_model(
            ...     experiment_id="exp-001",
            ...     model_path="/tmp/resnet50.pt",
            ...     name="resnet50_v1",
            ...     tags=["production", "v1"],
            ... )
            >>> model
            Model(
                id="model-abc",
                name="resnet50_v1",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                tags=["production", "v1"],
                path="/storage/exp-001/models/resnet50_v1.pt",
                experiment_id="exp-001",
            )
            >>> dest_path
            "/storage/exp-001/models/resnet50_v1.pt"
        """
        self._ensure_experiment_initialized(experiment_id)

        import shutil

        exp_dir = self._get_experiment_dir(experiment_id)
        models_dir = exp_dir / "models"
        models_dir.mkdir(exist_ok=True)

        source = Path(model_path)
        dest = models_dir / source.name
        shutil.copy2(source, dest)

        model_id = str(uuid.uuid4())
        tags_json = json.dumps(tags) if tags else None

        rel_path = str(dest.relative_to(self.base_path))

        conn = self._get_meta_connection()
        cursor = conn.cursor()
        size = dest.stat().st_size

        cursor.execute(
            "INSERT INTO models (id, name, tags, path, size, experiment_id) VALUES (?, ?, ?, ?, ?, ?)",
            (model_id, name or source.stem, tags_json, rel_path, size, experiment_id),
        )
        conn.commit()

        now = datetime.now(UTC)
        model = Model(
            id=model_id,
            name=name or source.stem,
            created_at=now,
            tags=tags or [],
            path=rel_path,
            size=size,
            experiment_id=experiment_id,
        )
        return model, str(dest)

    def get_models(self, experiment_id: str) -> list[Model]:
        """
        Fetches all models associated with a given experiment ID.

        This method queries the database for all models that are linked to the
        specified experiment ID. Each row fetched from the database is converted
        to a `Model` object and returned as part of a list.

        Args:
            experiment_id (str): The identifier of the experiment whose models
                need to be fetched.

        Returns:
            list[Model]: A list of `Model` objects associated with the given
                experiment ID.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_models("exp-001")
            [
                Model(
                    id="model-abc",
                    name="resnet50_v1",
                    created_at=datetime(2024, 6, 1, 12, 0, 0),
                    tags=["production", "v1"],
                    path="/artifacts/resnet50_v1.pt",
                    experiment_id="exp-001",
                ),
                Model(
                    id="model-def",
                    name="resnet50_v2",
                    created_at=datetime(2024, 6, 2, 9, 0, 0),
                    tags=[],
                    path=None,
                    experiment_id="exp-001",
                ),
            ]
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at, tags, path, size, experiment_id FROM models WHERE experiment_id = ?",
            (experiment_id,),
        )
        return [self._row_to_model(row) for row in cursor.fetchall()]

    def get_model(self, model_id: str) -> Model:
        """
        Retrieves a model instance based on the provided model ID.

        Uses an internal meta connection to locate and fetch the model by the
        given model ID. If the model does not exist, a ValueError is raised.

        Args:
            model_id (str): The unique identifier of the model to retrieve.

        Returns:
            Model: The retrieved model instance.

        Raises:
            ValueError: If the model with the specified ID is not found.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_model("model-abc")
            Model(
                id="model-abc",
                name="resnet50_v1",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                tags=["production", "v1"],
                path="/artifacts/resnet50_v1.pt",
                experiment_id="exp-001",
            )

            >>> backend.get_model("nonexistent-id")
            ValueError: Model nonexistent-id not found
        """
        conn = self._get_meta_connection()
        model = self._fetch_model(conn.cursor(), model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")
        return model

    def update_model(
        self,
        model_id: str,
        name: str | None = None,
        tags: list[str] | None = None,
    ) -> Model | None:
        """
        Updates the attributes of a model in the database given its model ID.

        This method allows updating the name and tags of a model. If no fields are
        provided for updating, it fetches and returns the original model. The tags,
        if provided, are stored as a JSON string in the database.

        Args:
            model_id (str): The unique identifier of the model to update.
            name (str | None): The new name for the model. Defaults to None.
            tags (list[str] | None): A list of string tags to associate with the model.
                Defaults to None.

        Returns:
            Model | None: The updated model as a `Model` object if the update is
            successful, or None if the model with the given ID does not exist.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.update_model("model-abc", name="resnet50_v2", tags=["production", "v2"])
            Model(
                id="model-abc",
                name="resnet50_v2",
                created_at=datetime(2024, 6, 1, 12, 0, 0),
                tags=["production", "v2"],
                path="/artifacts/resnet50_v1.pt",
                experiment_id="exp-001",
            )

            >>> backend.update_model("nonexistent-id")
            None
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        fields: list[str] = []
        values: list[Any] = []

        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags))

        if not fields:
            return self._fetch_model(cursor, model_id)

        values.append(model_id)
        cursor.execute(
            f"UPDATE models SET {', '.join(fields)} WHERE id = ?",  # noqa: S608
            values,
        )
        conn.commit()

        return self._fetch_model(cursor, model_id)

    def delete_model(self, model_id: str) -> None:
        """
        Deletes a model and its files from the database and filesystem.

        The method removes a model entry from the database and, if a file path for the
        model exists, deletes the associated file from the specified directory.

        Args:
            model_id (str): The unique identifier of the model to be deleted.
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        if row and row[0]:
            model_file = self.base_path / row[0]
            if model_file.exists():
                model_file.unlink()

        cursor.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()

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
                ("name LIKE ? OR tags LIKE ?", [f"%{search}%", f"%{search}%"])
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
                tags=d["tags"] if d["tags"] else [],
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

    def list_batch_experiments_models(
        self, experiment_ids: list[str]
    ) -> dict[str, list[Model]]:
        """
        Retrieves models associated with a list of experiment IDs. Models are organized into a dictionary
        where the key is the experiment ID, and the value is a list of `Model` objects belonging to that
        experiment. If no experiment IDs are provided, an empty dictionary is returned.

        Args:
            experiment_ids (list[str]): A list of experiment IDs for which models need to be fetched.

        Returns:
            dict[str, list[Model]]: A dictionary where keys are experiment IDs and values are lists of
            models associated with those experiment IDs.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.list_batch_experiments_models(["exp-001", "exp-002"])
            {
                "exp-001": [
                    Model(
                        id="model-abc",
                        name="resnet50_v1",
                        created_at=datetime(2024, 6, 1, 12, 0, 0),
                        tags=["production"],
                        path="/artifacts/resnet50_v1.pt",
                        experiment_id="exp-001",
                    ),
                ],
                "exp-002": [
                    Model(
                        id="model-def",
                        name="bert_base",
                        created_at=datetime(2024, 6, 2, 9, 0, 0),
                        tags=[],
                        path=None,
                        experiment_id="exp-002",
                    ),
                ],
            }
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        models_by_experiment: dict[str, list[Model]] = {}
        if experiment_ids:
            placeholders = ", ".join("?" for _ in experiment_ids)

            cursor.execute(
                f"SELECT id, name, created_at, tags, path, size, experiment_id FROM models WHERE experiment_id IN ({placeholders})",
                experiment_ids,
            )
            for row in cursor.fetchall():
                models_by_experiment.setdefault(row[5], []).append(
                    self._row_to_model(row)
                )

        return models_by_experiment

    def list_experiment_models(self, experiment_id: str) -> list[Model]:
        """
        Fetches a list of models associated with the specified experiment.

        This method queries the database for all models tied to an experiment identified
        by the provided `experiment_id`. Each model is returned as an instance of the
        `Model` class. The models include details such as their IDs, names, creation
        timestamps, tags, associated paths, and experiment IDs.

        Args:
            experiment_id (str): The unique identifier of the experiment whose
                models are to be retrieved.

        Returns:
            list[Model]: A list of `Model` instances representing the models
                associated with the specified experiment.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.list_experiment_models("exp-001")
            [
                Model(
                    id="model-abc",
                    name="resnet50_v1",
                    created_at=datetime(2024, 6, 1, 12, 0, 0),
                    tags=["production", "v1"],
                    path="/artifacts/resnet50_v1.pt",
                    experiment_id="exp-001",
                ),
                Model(
                    id="model-def",
                    name="resnet50_v2",
                    created_at=datetime(2024, 6, 1, 14, 30, 0),
                    tags=[],
                    path=None,
                    experiment_id="exp-001",
                ),
            ]
        """
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, created_at, tags, path, size, experiment_id FROM models WHERE experiment_id = ?",
            (experiment_id,),
        )

        return [self._row_to_model(row) for row in cursor.fetchall()]

    def validate_experiments_search(self, search: str | None = None) -> None:
        return SearchExperimentsUtils.validate_filter_string(search)

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

        rows = self._execute_paginated_query(
            conn=conn,
            table="experiments",
            columns=self._EXPERIMENT_COLUMNS,
            limit=limit,
            sort_by=sort_by,
            order=order,
            cursor_id=use_cursor.id if use_cursor else None,
            cursor_value=str(use_cursor.value)
            if use_cursor and use_cursor.value is not None
            else None,
            where=where_conditions,
            json_sort_column=json_sort_column,
            allowed_sort_columns=self._STANDARD_EXPERIMENT_SORT_COLUMNS,
        )

        experiments_dicts = self._items_to_dict(self._EXPERIMENT_COLUMNS, rows)
        models_by_experiment = self.list_batch_experiments_models(
            [e["id"] for e in experiments_dicts]
        )

        items = [
            Experiment(
                id=e["id"],
                group_id=e["group_id"],
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
            where_conditions.append(
                ("name LIKE ? OR tags LIKE ?", [f"%{search}%", f"%{search}%"])
            )
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
        Fetches a paginated list of experiments across multiple groups, supporting various
        sorting, filtering, and cursor-based pagination options.

        This method retrieves experiments associated with the provided group IDs, ordering and
        filtering them based on the given parameters. It supports sorting by both standard
        columns and specific JSON fields, as well as filtering based on search terms and
        cursor-based pagination. Returns an empty response if the group list is empty.

        Args:
            group_ids (list[str]): The list of group identifiers whose experiments are being
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
            where_conditions.append(
                ("name LIKE ? OR tags LIKE ?", [f"%{search}%", f"%{search}%"])
            )
        return self._build_experiments_page(
            where_conditions, limit, sort_by, order, cursor_str, json_sort_column
        )

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
        Retrieves the historical metrics data for a specific experiment and metric key. The data
        is ordered by the step value in ascending order. Each metric record contains the value,
        step, and timestamp when the metric was logged.

        Args:
            experiment_id: The unique identifier for the experiment whose metric history is
                being retrieved.
            key: The key for the metric whose history is being fetched.

        Returns:
            A list of dictionaries where each dictionary contains the following keys:
                - 'value' (Any): The stored value of the metric.
                - 'step' (int): The step or index associated with the metric value.
                - 'logged_at' (datetime): A timestamp representing when the metric was logged.

        Raises:
            ValueError: If the experiment with the given `experiment_id` does not exist.
        """
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")
        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value, step, logged_at FROM dynamic_metrics WHERE key = ? ORDER BY step",
            (key,),
        )
        return [
            {"value": value, "step": step, "logged_at": logged_at}
            for value, step, logged_at in cursor.fetchall()
        ]

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
            where_conditions.append(("trace_id LIKE ?", [f"%{search}%"]))

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
                execution_time=row[1] / 1_000_000_000,
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
            where_clauses.append("trace_id LIKE ?")
            params.append(f"%{search}%")
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
                execution_time=row[1] / 1_000_000_000,
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
            where_conditions.append(("id LIKE ?", [f"%{search}%"]))

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

        conn = self._get_experiment_connection(experiment_id)

        where_clauses: list[str] = []
        params: list[Any] = []

        if dataset_id:
            where_clauses.append("dataset_id = ?")
            params.append(dataset_id)
        if search:
            where_clauses.append("id LIKE ?")
            params.append(f"%{search}%")

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

    def get_experiment_eval_dataset_ids(self, experiment_id: str) -> list[str]:
        conn = self._get_experiment_connection(experiment_id)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT dataset_id FROM evals ORDER BY dataset_id")
        return [row[0] for row in cur.fetchall()]

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

    def _has_annotation_tables(self, experiment_id: str) -> bool:
        conn = self._get_experiment_connection(experiment_id)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        return version >= 1

    def _require_annotation_tables(self, experiment_id: str) -> None:
        if not self._has_annotation_tables(experiment_id):
            raise ValueError(
                f"Experiment '{experiment_id}' uses an older schema that "
                "does not support annotations. Re-create the experiment "
                "to enable annotation support."
            )

    @staticmethod
    def _serialize_annotation_value(value: int | bool | str) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def _deserialize_annotation_value(
        raw: str, value_type: AnnotationValueType
    ) -> int | bool | str:
        if value_type == AnnotationValueType.BOOL:
            return raw.lower() == "true"
        if value_type == AnnotationValueType.INT:
            return int(raw)
        return raw

    @staticmethod
    def _row_to_annotation(row: sqlite3.Row) -> AnnotationRecord:
        vt = AnnotationValueType(row[5])
        return AnnotationRecord(
            id=row[0],
            name=row[1],
            annotation_kind=AnnotationKind(row[2]),
            value_type=vt,
            value=SQLiteBackend._deserialize_annotation_value(row[3], vt),
            user=row[4],
            created_at=row[6],
            rationale=row[7],
        )

    @staticmethod
    def _validate_feedback_value_type(
        annotation_kind: AnnotationKind, value_type: AnnotationValueType
    ) -> None:
        if (
            annotation_kind == AnnotationKind.FEEDBACK
            and value_type != AnnotationValueType.BOOL
        ):
            raise ValueError("Feedback annotations must use value_type='bool'")

    def log_eval_annotation(
        self,
        experiment_id: str,
        dataset_id: str,
        eval_id: str,
        name: str,
        annotation_kind: AnnotationKind,
        value_type: AnnotationValueType,
        value: int | bool | str,
        user: str,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        """
        Logs an annotation for a specific evaluation within an experiment and records it in the database.

        This function stores metadata, rationale, and value of the annotation associated with a specific
        evaluation ID. It ensures the consistency of the annotation's type and validates the necessary
        conditions before committing the record into the database.

        Args:
            experiment_id (str): The id of the experiment.
            dataset_id (str): The id of the dataset within the experiment.
            eval_id (str): The id of the eval within the dataset.
            name (str): The name of the annotation being logged.
            annotation_kind (AnnotationKind): The type of the annotation
            value_type (AnnotationValueType): Defines the expected type of the annotation value.
            value (int | bool | str): The actual value of the annotation.
            user (str): The user who created the annotation.
            rationale (str | None): The rationale or reasoning behind the annotation, if applicable.

        Returns:
            AnnotationRecord: Object containing the logged annotation's details from the database.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> record = backend.log_eval_annotation(
            ...     experiment_id="exp-001",
            ...     dataset_id="dataset-abc",
            ...     eval_id="eval-xyz",
            ...     name="quality",
            ...     annotation_kind=AnnotationKind.FEEDBACK,
            ...     value_type=AnnotationValueType.BOOL,
            ...     value=True,
            ...     user="alice",
            ...     rationale="Looks correct",
            ... )
            AnnotationRecord(
                id="annot-001",
                name="quality",
                annotation_kind=AnnotationKind.FEEDBACK,
                value=True,
                user="alice",
                value_type=AnnotationValueType.BOOL,
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                rationale="Looks correct"
            )
        """
        self._validate_feedback_value_type(annotation_kind, value_type)
        self._require_annotation_tables(experiment_id)
        annotation_id = str(uuid.uuid4())
        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            conn.execute(
                """INSERT INTO eval_annotations
                   (id, dataset_id, eval_id, name, annotation_kind, value_type, value, user, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    annotation_id,
                    dataset_id,
                    eval_id,
                    name,
                    annotation_kind.value,
                    value_type.value,
                    self._serialize_annotation_value(value),
                    user,
                    rationale,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
                   FROM eval_annotations WHERE id = ?""",
                (annotation_id,),
            ).fetchone()
        return self._row_to_annotation(row)

    def get_eval_annotations(
        self, experiment_id: str, dataset_id: str, eval_id: str
    ) -> list[AnnotationRecord]:
        """
        Retrieves evaluation annotations associated with a specific experiment, dataset,
        and evaluation identifier. The annotations are fetched from a database table and
        returned as a list of AnnotationRecord objects.

        Args:
            experiment_id: Unique identifier for the experiment.
            dataset_id: Unique identifier for the dataset within the experiment.
            eval_id: Unique identifier for the evaluation phase.

        Returns:
            A list of AnnotationRecord objects representing the annotations retrieved for the
            specified dataset and evaluation phase. Returns an empty list if annotation
            tables are not available for the given experiment.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_eval_annotations("exp-001", "dataset-abc", "eval-xyz")
            [
                AnnotationRecord(
                    id="annot-001",
                    name="quality",
                    annotation_kind=AnnotationKind.FEEDBACK,
                    value=True,
                    user="alice",
                    value_type=AnnotationValueType.BOOL,
                    created_at=datetime(2024, 6, 1, 10, 0, 0),
                    rationale="Looks correct"
                )
            ]
        """
        if not self._has_annotation_tables(experiment_id):
            return []
        conn = self._get_experiment_connection(experiment_id)
        rows = conn.execute(
            """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
               FROM eval_annotations
               WHERE dataset_id = ? AND eval_id = ?
               ORDER BY created_at""",
            (dataset_id, eval_id),
        ).fetchall()
        return [self._row_to_annotation(r) for r in rows]

    def log_span_annotation(
        self,
        experiment_id: str,
        trace_id: str,
        span_id: str,
        name: str,
        annotation_kind: AnnotationKind,
        value_type: AnnotationValueType,
        value: int | bool | str,
        user: str,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        """
        Logs a span annotation for a specific experiment, enabling traceability and observability within
        the system. This method ensures that the provided annotation is valid, persists the annotation
        data in the experiment database, and retrieves the newly created annotation record.

        Args:
            experiment_id (str): Identifier for the experiment where the annotation will be logged.
            trace_id (str): Identifier for the trace to which the span belongs.
            span_id (str): Identifier for the span to be annotated.
            name (str): Name of the annotation being logged.
            annotation_kind (AnnotationKind): Type or category of the annotation, specifying its role or
                purpose.
            value_type (AnnotationValueType): Data type of the annotation's value, ensuring compatibility
                and validity.
            value (int | bool | str): The actual value associated with the annotation, adhering to the
                specified value type.
            user (str): Identifier of the user or system initiating the creation of the annotation.
            rationale (str | None): Optional explanation or justification for the annotation.

        Returns:
            AnnotationRecord: An object containing the details of the newly created annotation, including
            associated metadata and identifier.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> record = backend.log_span_annotation(
            ...     experiment_id="exp-001",
            ...     trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
            ...     span_id="span-abc",
            ...     name="latency_ok",
            ...     annotation_kind=AnnotationKind.FEEDBACK,
            ...     value_type=AnnotationValueType.BOOL,
            ...     value=True,
            ...     user="alice",
            ... )
            AnnotationRecord(
                id="annot-002",
                name="latency_ok",
                annotation_kind=AnnotationKind.FEEDBACK,
                value=True,
                user="alice",
                value_type=AnnotationValueType.BOOL,
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                rationale=None,
            )
        """
        self._validate_feedback_value_type(annotation_kind, value_type)
        self._require_annotation_tables(experiment_id)
        annotation_id = str(uuid.uuid4())
        write_lock = self._get_experiment_write_lock(experiment_id)
        with write_lock:
            conn = self._get_experiment_connection(experiment_id)
            conn.execute(
                """INSERT INTO span_annotations
                   (id, trace_id, span_id, name, annotation_kind, value_type, value, user, rationale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    annotation_id,
                    trace_id,
                    span_id,
                    name,
                    annotation_kind.value,
                    value_type.value,
                    self._serialize_annotation_value(value),
                    user,
                    rationale,
                ),
            )
            conn.commit()
            row = conn.execute(
                """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
                   FROM span_annotations WHERE id = ?""",
                (annotation_id,),
            ).fetchone()
        return self._row_to_annotation(row)

    def get_span_annotations(
        self, experiment_id: str, trace_id: str, span_id: str
    ) -> list[AnnotationRecord]:
        """
        Fetches annotations for a specific span in a trace within the context of an experiment.

        This method retrieves all annotations associated with a span, identified by its trace
        and span IDs, within a given experiment. The annotations are returned as a list of
        `AnnotationRecord` objects, sorted by their creation timestamp. If no annotation tables
        exist for the given experiment, an empty list is returned.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            trace_id (str): The unique identifier of the trace.
            span_id (str): The unique identifier of the span whose annotations are to be fetched.

        Returns:
            list[AnnotationRecord]: A list of annotations for the specified span. If no
            annotations are found, the returned list will be empty.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_span_annotations(
            ...     "exp-001",
            ...     "4bf92f3577b34da6a3ce929d0e0e4736",
            ...     "span-abc",
            ... )
            [
                AnnotationRecord(
                    id="annot-002",
                    name="latency_ok",
                    annotation_kind=AnnotationKind.FEEDBACK,
                    value=True,
                    user="alice",
                    value_type=AnnotationValueType.BOOL,
                    created_at=datetime(2024, 6, 1, 10, 0, 0),
                    rationale=None
                )
            ]
        """
        if not self._has_annotation_tables(experiment_id):
            return []
        conn = self._get_experiment_connection(experiment_id)
        rows = conn.execute(
            """SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale
               FROM span_annotations
               WHERE trace_id = ? AND span_id = ?
               ORDER BY created_at""",
            (trace_id, span_id),
        ).fetchall()
        return [self._row_to_annotation(r) for r in rows]

    def update_annotation(
        self,
        experiment_id: str,
        annotation_id: str,
        target: Literal["eval", "span"],
        value: int | bool | str | None = None,
        rationale: str | None = None,
    ) -> AnnotationRecord:
        """
        Updates an annotation record in the specified table with the provided fields.

        This method allows modification of an existing annotation record by updating its
        `value` and/or `rationale` fields in the corresponding database table. The table is
        selected based on the target type ("eval" or "span"). If no fields are provided for
        update, an error is raised.

        Args:
            experiment_id (str): The unique identifier for the experiment associated with the
                annotation.
            annotation_id (str): The unique identifier for the annotation to be updated.
            target (Literal["eval", "span"]): Specifies the annotation table to use. "eval"
                refers to evaluation annotations and "span" refers to span annotations.
            value (int | bool | str | None, optional): The new value to set for the annotation.
                If not provided, the value field will not be updated.
            rationale (str | None, optional): The new rationale to set for the annotation. If
                not provided, the rationale field will not be updated.

        Returns:
            AnnotationRecord: An updated annotation record object after the update operation.

        Raises:
            ValueError: If no fields (`value` or `rationale`) are specified for update or if
                the specified annotation does not exist in the database.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.update_annotation(
            ...     experiment_id="exp-001",
            ...     annotation_id="annot-001",
            ...     target="eval",
            ...     value=False,
            ...     rationale="Reconsidered after review",
            ... )
            AnnotationRecord(
                id="annot-001",
                name="quality",
                annotation_kind=AnnotationKind.FEEDBACK,
                value=False,
                user="alice",
                value_type=AnnotationValueType.BOOL,
                created_at=datetime(2024, 6, 1, 10, 0, 0),
                rationale="Reconsidered after review",
            )
        """
        self._require_annotation_tables(experiment_id)
        table = "eval_annotations" if target == "eval" else "span_annotations"
        conn = self._get_experiment_connection(experiment_id)

        sets: list[str] = []
        params: list[str] = []
        if value is not None:
            sets.append("value = ?")
            params.append(self._serialize_annotation_value(value))
        if rationale is not None:
            sets.append("rationale = ?")
            params.append(rationale)
        if not sets:
            raise ValueError("No fields to update")

        params.append(annotation_id)
        conn.execute(
            f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        conn.commit()
        row = conn.execute(
            f"SELECT id, name, annotation_kind, value, user, value_type, created_at, rationale FROM {table} WHERE id = ?",  # noqa: S608
            (annotation_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Annotation '{annotation_id}' not found")
        return self._row_to_annotation(row)

    def delete_annotation(
        self, experiment_id: str, annotation_id: str, target: Literal["eval", "span"]
    ) -> None:
        """
        Deletes a specific annotation from the database for a given experiment.

        This method removes an annotation identified by its annotation_id from the
        appropriate table associated with the target type (either "eval" or "span")
        within the specified experiment. If the experiment does not have annotation
        tables, the method exits without performing any operation.

        Args:
            experiment_id (str): The unique identifier for the experiment.
            annotation_id (str): The unique identifier for the annotation to be deleted.
            target (Literal["eval", "span"]): Specifies the target table from which the
                annotation should be deleted. Must be either "eval" or "span".

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.delete_annotation("exp-001", "annot-001", target="eval")
        """
        if not self._has_annotation_tables(experiment_id):
            return
        table = "eval_annotations" if target == "eval" else "span_annotations"
        conn = self._get_experiment_connection(experiment_id)
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (annotation_id,))  # noqa: S608
        conn.commit()

    @staticmethod
    def _build_annotation_summary(
        feedback_rows: list[sqlite3.Row],
        expectation_rows: list[sqlite3.Row],
    ) -> AnnotationSummary:
        """
        Builds an annotation summary from feedback and expectation data.

        The method processes two sets of rows: feedback data and expectation
        data, aggregating and casting values where appropriate, to create a
        structured summary.

        Args:
            feedback_rows (list[sqlite3.Row]): A list of sqlite3.Row objects representing
                feedback data. Each row should contain name, value, and count.
            expectation_rows (list[sqlite3.Row]): A list of sqlite3.Row objects representing
                expectation data. Each row should contain name, total, positive, negative,
                and raw value information.

        Returns:
            AnnotationSummary: A structured summary of the feedback and expectations,
            including aggregated feedback items and processed expectation details.
        """

        feedback_items: dict[str, FeedbackSummaryItem] = {}
        for row in feedback_rows:
            name, value, count = row[0], row[1], row[2]
            if name not in feedback_items:
                feedback_items[name] = FeedbackSummaryItem(
                    name=name, total=0, counts={}
                )
            item = feedback_items[name]
            item.total += count
            item.counts[value] = count

        def _cast_value(raw: str | None, value_type: str | None) -> int | str | None:
            if raw is None:
                return None
            if value_type == "int":
                return int(raw)
            return raw

        return AnnotationSummary(
            feedback=sorted(feedback_items.values(), key=lambda x: x.name),
            expectations=[
                ExpectationSummaryItem(
                    name=row[0],
                    total=row[1],
                    positive=row[2],
                    negative=row[3],
                    value=_cast_value(row[4], row[5]),
                )
                for row in expectation_rows
            ],
        )

    def get_evals_annotation_summaries(
        self, experiment_id: str, eval_ids: list[str]
    ) -> dict[str, AnnotationSummary]:
        """
        Retrieves annotation summaries for a batch of evaluations within an experiment.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            eval_ids (list[str]): A list of evaluation IDs to retrieve summaries for.

        Returns:
            dict[str, AnnotationSummary]: A dictionary mapping each eval ID to its annotation
            summary. Eval IDs with no annotations are excluded from the result.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_evals_annotation_summaries("exp-001", ["eval-xyz", "eval-abc"])
            {
                "eval-xyz": AnnotationSummary(
                    feedback=[FeedbackSummaryItem(name="quality", total=2, counts={"true": 1, "false": 1})],
                    expectations=[],
                ),
            }
        """
        if not self._has_annotation_tables(experiment_id) or not eval_ids:
            return {}
        conn = self._get_experiment_connection(experiment_id)
        feedback_by_eval: dict[str, list] = {}
        expectation_by_eval: dict[str, list] = {}
        for i in range(0, len(eval_ids), 900):
            batch = eval_ids[i : i + 900]
            placeholders = ",".join("?" * len(batch))
            for row in conn.execute(
                f"""SELECT eval_id, name, value, COUNT(*) AS cnt
                   FROM eval_annotations
                   WHERE eval_id IN ({placeholders}) AND annotation_kind = 'feedback'
                   GROUP BY eval_id, name, value
                   ORDER BY name, value""",
                batch,
            ).fetchall():
                feedback_by_eval.setdefault(row[0], []).append(row[1:])
            for row in conn.execute(
                f"""SELECT eval_id, name, COUNT(*) AS total,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                       MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                       MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
                   FROM eval_annotations
                   WHERE eval_id IN ({placeholders}) AND annotation_kind = 'expectation'
                   GROUP BY eval_id, name
                   ORDER BY name""",
                batch,
            ).fetchall():
                expectation_by_eval.setdefault(row[0], []).append(row[1:])
        return {
            eval_id: self._build_annotation_summary(
                feedback_by_eval.get(eval_id, []),
                expectation_by_eval.get(eval_id, []),
            )
            for eval_id in eval_ids
            if eval_id in feedback_by_eval or eval_id in expectation_by_eval
        }

    def get_eval_annotation_summary(
        self, experiment_id: str, dataset_id: str
    ) -> AnnotationSummary:
        """
        Retrieves a summary of evaluation annotations for a specific experiment and dataset.

        This method queries annotation data associated with the provided experiment
        and dataset identifiers, specifically gathering details about feedback and
        expectation annotations. Feedback annotations provide a count of distinct
        name-value pairs, while expectation annotations summarize details such as
        total occurrences, positive and negative boolean counts, and sample values
        for non-boolean annotations.

        Args:
            experiment_id (str): Unique identifier for the experiment to retrieve
                annotation data from.
            dataset_id (str): Unique identifier for the dataset within the specified
                experiment.

        Returns:
            AnnotationSummary: A summary of feedback and expectations contained in
                the evaluation annotations for the given experiment and dataset.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_eval_annotation_summary("exp-001", "dataset-abc")
            AnnotationSummary(
                feedback=[FeedbackSummaryItem(name="quality", total=3, counts={"true": 2, "false": 1})],
                expectations=[],
            )
        """
        if not self._has_annotation_tables(experiment_id):
            return AnnotationSummary(feedback=[], expectations=[])
        conn = self._get_experiment_connection(experiment_id)
        feedback_rows = conn.execute(
            """SELECT name, value, COUNT(*) AS cnt
               FROM eval_annotations
               WHERE dataset_id = ? AND annotation_kind = 'feedback'
               GROUP BY name, value
               ORDER BY name, value""",
            (dataset_id,),
        ).fetchall()
        expectation_rows = conn.execute(
            """SELECT name, COUNT(*) AS total,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                   MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                   MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
               FROM eval_annotations
               WHERE dataset_id = ? AND annotation_kind = 'expectation'
               GROUP BY name
               ORDER BY name""",
            (dataset_id,),
        ).fetchall()
        return self._build_annotation_summary(feedback_rows, expectation_rows)

    def get_traces_annotation_summaries(
        self, experiment_id: str, trace_ids: list[str]
    ) -> dict[str, AnnotationSummary]:
        """
        Retrieves annotation summaries for specified traces in a given experiment. This method aggregates
        feedback and expectation annotations for each trace, combining them to build summaries of annotations.
        For annotation kinds, 'feedback' aggregates counts of values, while 'expectation' provides both
        aggregate counts and value-specific information.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            trace_ids (list[str]): A list of trace IDs for which annotation summaries are to be retrieved.

        Returns:
            dict[str, AnnotationSummary]: A dictionary mapping each trace ID to its annotation summary.
            If no annotations are present, or the input trace list is empty, an empty dictionary is returned.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_traces_annotation_summaries(
            ...     "exp-001",
            ...     ["4bf92f3577b34da6a3ce929d0e0e4736", "5bf92f3577b34da6a3ce929d0e0e4737"],
            ... )
            {
                "4bf92f3577b34da6a3ce929d0e0e4736": AnnotationSummary(
                    feedback=[FeedbackSummaryItem(name="latency_ok", total=1, counts={"true": 1})],
                    expectations=[],
                ),
            }
        """
        if not self._has_annotation_tables(experiment_id) or not trace_ids:
            return {}
        conn = self._get_experiment_connection(experiment_id)
        feedback_by_trace: dict[str, list] = {}
        expectation_by_trace: dict[str, list] = {}
        for i in range(0, len(trace_ids), 900):
            batch = trace_ids[i : i + 900]
            placeholders = ",".join("?" * len(batch))
            for row in conn.execute(
                f"""SELECT trace_id, name, value, COUNT(*) AS cnt
                   FROM span_annotations
                   WHERE trace_id IN ({placeholders}) AND annotation_kind = 'feedback'
                   GROUP BY trace_id, name, value
                   ORDER BY name, value""",
                batch,
            ).fetchall():
                feedback_by_trace.setdefault(row[0], []).append(row[1:])
            for row in conn.execute(
                f"""SELECT trace_id, name, COUNT(*) AS total,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                       SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                       MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                       MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
                   FROM span_annotations
                   WHERE trace_id IN ({placeholders}) AND annotation_kind = 'expectation'
                   GROUP BY trace_id, name
                   ORDER BY name""",
                batch,
            ).fetchall():
                expectation_by_trace.setdefault(row[0], []).append(row[1:])
        return {
            trace_id: self._build_annotation_summary(
                feedback_by_trace.get(trace_id, []),
                expectation_by_trace.get(trace_id, []),
            )
            for trace_id in trace_ids
            if trace_id in feedback_by_trace or trace_id in expectation_by_trace
        }

    def get_trace_annotation_summary(
        self, experiment_id: str, trace_id: str
    ) -> AnnotationSummary:
        """
        Retrieves the annotation summary for a specific trace in a given experiment. The summary includes
        feedback and expectation annotations grouped by name and processed according to their type and values.

        Args:
            experiment_id (str): The unique identifier of the experiment.
            trace_id (str): The unique identifier of the trace.

        Returns:
            AnnotationSummary: An object containing summarized feedback and expectations annotations
            for the specified trace.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_trace_annotation_summary("exp-001", "4bf92f3577b34da6a3ce929d0e0e4736")
            AnnotationSummary(
                feedback=[FeedbackSummaryItem(name="latency_ok", total=1, counts={"true": 1})],
                expectations=[],
            )
        """
        if not self._has_annotation_tables(experiment_id):
            return AnnotationSummary(feedback=[], expectations=[])
        conn = self._get_experiment_connection(experiment_id)
        feedback_rows = conn.execute(
            """SELECT name, value, COUNT(*) AS cnt
               FROM span_annotations
               WHERE trace_id = ? AND annotation_kind = 'feedback'
               GROUP BY name, value
               ORDER BY name, value""",
            (trace_id,),
        ).fetchall()
        expectation_rows = conn.execute(
            """SELECT name, COUNT(*) AS total,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                   MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                   MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
               FROM span_annotations
               WHERE trace_id = ? AND annotation_kind = 'expectation'
               GROUP BY name
               ORDER BY name""",
            (trace_id,),
        ).fetchall()
        return self._build_annotation_summary(feedback_rows, expectation_rows)

    def get_all_traces_annotation_summary(
        self, experiment_id: str
    ) -> AnnotationSummary:
        """
        Retrieves an annotation summary, including detailed feedback and expectation statistics, for a
        specified experiment given its identifier.

        This method extracts and organizes data from the annotation tables of an experiment, if available,
        to generate a summary of the feedback and expectations associated with that experiment. If the
        annotation tables are not present, it will return an empty summary object.

        Args:
            experiment_id (str): The unique identifier of the experiment from which annotation data
                will be retrieved.

        Returns:
            AnnotationSummary: A summary object containing feedback-related statistics and expectation
                values derived from the experiment's annotations.

        Example:
            >>> backend = SQLiteBackend("/backend/path")
            >>> backend.get_all_traces_annotation_summary("exp-001")
            AnnotationSummary(
                feedback=[
                    FeedbackSummaryItem(
                        name="latency_ok",
                        total=5,
                        counts={"true": 4, "false": 1}
                    )
                ],
                expectations=[]
            )
        """
        if not self._has_annotation_tables(experiment_id):
            return AnnotationSummary(feedback=[], expectations=[])
        conn = self._get_experiment_connection(experiment_id)
        feedback_rows = conn.execute(
            """SELECT name, value, COUNT(*) AS cnt
               FROM span_annotations
               WHERE annotation_kind = 'feedback'
               GROUP BY name, value
               ORDER BY name, value""",
        ).fetchall()
        expectation_rows = conn.execute(
            """SELECT name, COUNT(*) AS total,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'true' THEN 1 ELSE 0 END) AS positive,
                   SUM(CASE WHEN value_type = 'bool' AND value = 'false' THEN 1 ELSE 0 END) AS negative,
                   MAX(CASE WHEN value_type != 'bool' THEN value END) AS sample_value,
                   MAX(CASE WHEN value_type != 'bool' THEN value_type END) AS sample_value_type
               FROM span_annotations
               WHERE annotation_kind = 'expectation'
               GROUP BY name
               ORDER BY name""",
        ).fetchall()
        return self._build_annotation_summary(feedback_rows, expectation_rows)

    def get_experiment_ddl_version(self, experiment_id: str) -> int:
        db_path = self._get_experiment_db_path(experiment_id)
        conn = self.pool.get_connection(db_path)
        row = conn.execute("PRAGMA user_version").fetchone()
        return row[0] if row else 0
