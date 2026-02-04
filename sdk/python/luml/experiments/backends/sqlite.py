# flake8: noqa: E501
import atexit
import contextlib
import json
import sqlite3
import threading
import uuid
import weakref
from pathlib import Path
from typing import Any

from luml.artifacts._base import DiskFile, _BaseFile
from luml.experiments.backends._base import Backend
from luml.experiments.utils import guess_span_type
from luml.utils.tar import create_and_index_tar

_DDL_META_CREATE_EXPERIMENTS = """
    CREATE TABLE IF NOT EXISTS experiments (
        id TEXT PRIMARY KEY,
        name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'active',
        group_name TEXT,
        tags TEXT
)
"""
_DDL_META_CREATE_GROUPS = """
    CREATE TABLE IF NOT EXISTS experiment_groups (
        id TEXT PRIMARY KEY,
        name TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
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


class SQLiteBackend(Backend):
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

    def _initialize_meta_db(self) -> None:
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        cursor.execute(_DDL_META_CREATE_EXPERIMENTS)
        cursor.execute(_DDL_META_CREATE_GROUPS)

        conn.commit()

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
        name: str | None = None,
        group: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        conn = self._get_meta_connection()
        cursor = conn.cursor()

        tags_str = json.dumps(tags) if tags else None
        cursor.execute(
            """
            INSERT OR REPLACE INTO experiments (id, name, group_name, tags)
            VALUES (?, ?, ?, ?)
        """,
            (experiment_id, name or experiment_id, group, tags_str),
        )

        conn.commit()

        self._initialize_experiment_db(experiment_id)
        self.pool.mark_experiment_active(experiment_id)

    def log_static(self, experiment_id: str, key: str, value: Any) -> None:  # noqa: ANN401
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

    def get_experiment_data(self, experiment_id: str) -> dict[str, Any]:  # noqa: ANN401, C901
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")

        conn = self._get_experiment_connection(experiment_id)
        cursor = conn.cursor()

        cursor.execute("SELECT key, value, value_type FROM static_params")
        static_params = {}
        for key, value, value_type in cursor.fetchall():
            if value_type == "json":
                static_params[key] = json.loads(value)
            elif value_type == "int":
                static_params[key] = int(value)
            elif value_type == "float":
                static_params[key] = float(value)
            elif value_type == "bool":
                static_params[key] = value.lower() == "true"
            else:
                static_params[key] = value

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
            "SELECT name, created_at, status, group_name, tags FROM experiments WHERE id = ?",  # noqa: E501
            (experiment_id,),
        )
        meta_row = meta_cursor.fetchone()

        metadata = {}
        if meta_row:
            metadata = {
                "name": meta_row[0],
                "created_at": meta_row[1],
                "status": meta_row[2],
                "group": meta_row[3],
                "tags": json.loads(meta_row[4]) if meta_row[4] else [],
            }

        return {
            "experiment_id": experiment_id,
            "metadata": metadata,
            "static_params": static_params,
            "dynamic_metrics": dynamic_metrics,
            "attachments": attachments,
        }

    def get_attachment(self, experiment_id: str, name: str) -> Any:  # noqa: ANN401
        self._ensure_experiment_initialized(experiment_id)

        attachments_dir = self._get_attachments_dir(experiment_id)
        file_path = attachments_dir / name

        if not file_path.exists():
            raise ValueError(
                f"Attachment {name} not found in experiment {experiment_id}"
            )

        with file_path.open("rb") as f:
            return f.read()

    def list_experiments(self) -> list[dict[str, Any]]:  # noqa: ANN401
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, created_at, status, group_name, tags FROM experiments"
        )
        experiments = []
        for row in cursor.fetchall():
            experiments.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "created_at": row[2],
                    "status": row[3],
                    "group": row[4],
                    "tags": json.loads(row[5]) if row[5] else [],
                }
            )
        return experiments

    def delete_experiment(self, experiment_id: str) -> None:
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM experiments WHERE id = ?", (experiment_id,))
        conn.commit()

        self.pool.mark_experiment_inactive(experiment_id)

        exp_dir = self._get_experiment_dir(experiment_id)
        if exp_dir.exists():
            import shutil

            shutil.rmtree(exp_dir)

    def create_group(self, name: str, description: str | None = None) -> None:
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO experiment_groups (name, description)
            VALUES (?, ?)
        """,
            (name, description),
        )
        conn.commit()

    def list_groups(self) -> list[dict[str, Any]]:  # noqa: ANN401
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, created_at FROM experiment_groups")
        groups = []
        for row in cursor.fetchall():
            groups.append({"name": row[0], "description": row[1], "created_at": row[2]})
        return groups

    def end_experiment(self, experiment_id: str) -> None:
        conn = self._get_meta_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE experiments SET status = 'completed' WHERE id = ?", (experiment_id,)
        )
        conn.commit()

        self.pool.mark_experiment_inactive(experiment_id)

    def export_experiment_db(self, experiment_id: str) -> DiskFile:
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not found")
        with sqlite3.connect(db_path, check_same_thread=False) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        return DiskFile(db_path)

    def export_attachments(
        self, experiment_id: str
    ) -> tuple[_BaseFile, _BaseFile] | None:
        return create_and_index_tar(self._get_attachments_dir(experiment_id))
