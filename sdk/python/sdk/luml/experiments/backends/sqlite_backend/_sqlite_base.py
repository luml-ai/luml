import atexit
import contextlib
import json
import sqlite3
import threading
import weakref
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from luml.experiments.backends.data_types import (
    ColumnType,
)
from luml.experiments.backends.migration_runner import (
    ExperimentMigrationRunner,
    MetaDBMigrationRunner,
)
from luml.experiments.backends.sqlite_backend._sqlite_pagination_mixin import (
    SQLitePaginationMixin,
)


def _parse_timestamp(s: bytes) -> datetime:
    dt = datetime.fromisoformat(s.decode())
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _adapt_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


sqlite3.register_converter("TIMESTAMP", _parse_timestamp)
sqlite3.register_adapter(datetime, _adapt_datetime)


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

            conn = sqlite3.Connection(
                db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
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


class _SQLiteBase(SQLitePaginationMixin):
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

    _SQLITE_TYPE_MAP: dict[str, ColumnType] = {
        "text": ColumnType.STRING,
        "integer": ColumnType.NUMBER,
        "real": ColumnType.NUMBER,
        "true": ColumnType.BOOLEAN,
        "false": ColumnType.BOOLEAN,
    }

    _ANNOTATION_VALUE_TYPE_MAP: dict[str, ColumnType] = {
        "bool": ColumnType.BOOLEAN,
        "int": ColumnType.NUMBER,
        "string": ColumnType.STRING,
    }

    def __init__(
        self,
        config: str,
    ) -> None:
        self.base_path = Path(config)
        self.base_path.mkdir(exist_ok=True)
        self.meta_db_path = self.base_path / "meta.db"

        self.pool = ConnectionPool(10)
        self._migrated_experiment_dbs: set[str] = set()

        self._initialize_meta_db()
        weakref.finalize(self, self._cleanup)

    def _cleanup(self) -> None:
        if hasattr(self, "pool"):
            self.pool.close_all()

    def _ensure_experiment_initialized(self, experiment_id: str) -> None:
        db_path = self._get_experiment_db_path(experiment_id)
        if not db_path.exists():
            raise ValueError(f"Experiment {experiment_id} not initialized")
        if experiment_id not in self._migrated_experiment_dbs:
            conn = self._get_experiment_connection(experiment_id)
            ExperimentMigrationRunner(conn).migrate()
            self._migrated_experiment_dbs.add(experiment_id)

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
        MetaDBMigrationRunner(conn).migrate()

    def _initialize_experiment_db(self, experiment_id: str) -> None:
        exp_dir = self._get_experiment_dir(experiment_id)
        exp_dir.mkdir(exist_ok=True)
        self._get_attachments_dir(experiment_id).mkdir(exist_ok=True)

        conn = self.pool.get_connection(self._get_experiment_db_path(experiment_id))
        ExperimentMigrationRunner(conn).migrate()
        self._migrated_experiment_dbs.add(experiment_id)
