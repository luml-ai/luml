import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


class UploadStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PendingUpload:
    id: str
    run_id: str
    node_id: str
    model_path: str
    experiment_ids: list[str]
    file_size: int
    status: UploadStatus
    error: str | None = None
    retry_count: int = 0
    created_at: str = ""
    updated_at: str = ""


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    model_path TEXT NOT NULL,
    experiment_ids TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uploads_run_status
    ON uploads (run_id, status);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_upload(row: sqlite3.Row) -> PendingUpload:
    return PendingUpload(
        id=row["id"],
        run_id=row["run_id"],
        node_id=row["node_id"],
        model_path=row["model_path"],
        experiment_ids=json.loads(row["experiment_ids"]),
        file_size=row["file_size"],
        status=UploadStatus(row["status"]),
        error=row["error"],
        retry_count=row["retry_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class UploadQueue:
    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".luml-agent" / "uploads.db"
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def enqueue(
        self,
        run_id: str,
        node_id: str,
        model_path: str,
        experiment_ids: list[str],
    ) -> PendingUpload:
        path = Path(model_path)
        file_size = path.stat().st_size if path.exists() else 0
        upload_id = uuid4().hex
        now = _now()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO uploads "
                "(id, run_id, node_id, model_path, experiment_ids, "
                "file_size, status, retry_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (
                    upload_id,
                    run_id,
                    node_id,
                    model_path,
                    json.dumps(experiment_ids),
                    file_size,
                    UploadStatus.PENDING,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return PendingUpload(
            id=upload_id,
            run_id=run_id,
            node_id=node_id,
            model_path=model_path,
            experiment_ids=experiment_ids,
            file_size=file_size,
            status=UploadStatus.PENDING,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )

    def claim(self, upload_id: str) -> bool:
        now = _now()
        conn = self._connect()
        try:
            cursor = conn.execute(
                "UPDATE uploads SET status = ?, updated_at = ? "
                "WHERE id = ? AND status = ?",
                (UploadStatus.IN_PROGRESS, now, upload_id, UploadStatus.PENDING),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def complete(self, upload_id: str) -> None:
        now = _now()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE uploads SET status = ?, updated_at = ? WHERE id = ?",
                (UploadStatus.COMPLETED, now, upload_id),
            )
            conn.commit()
        finally:
            conn.close()

    def fail(self, upload_id: str, error: str) -> None:
        now = _now()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT retry_count FROM uploads WHERE id = ?",
                (upload_id,),
            ).fetchone()
            if row is None:
                return
            new_count = row["retry_count"] + 1
            new_status = (
                UploadStatus.FAILED if new_count >= 3 else UploadStatus.PENDING
            )
            conn.execute(
                "UPDATE uploads SET status = ?, error = ?, "
                "retry_count = ?, updated_at = ? WHERE id = ?",
                (new_status, error, new_count, now, upload_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_pending(self, run_id: str) -> list[PendingUpload]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM uploads WHERE run_id = ? AND status = ?",
                (run_id, UploadStatus.PENDING),
            ).fetchall()
            return [_row_to_upload(r) for r in rows]
        finally:
            conn.close()

    def get(self, upload_id: str) -> PendingUpload | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM uploads WHERE id = ?",
                (upload_id,),
            ).fetchone()
            return _row_to_upload(row) if row else None
        finally:
            conn.close()

    def get_active_for_nodes(self, node_ids: list[str]) -> list[PendingUpload]:
        if not node_ids:
            return []
        conn = self._connect()
        try:
            placeholders = ",".join("?" * len(node_ids))
            rows = conn.execute(
                f"SELECT * FROM uploads WHERE node_id IN ({placeholders}) "
                f"AND status IN (?, ?)",
                [*node_ids, UploadStatus.PENDING, UploadStatus.IN_PROGRESS],
            ).fetchall()
            return [_row_to_upload(r) for r in rows]
        finally:
            conn.close()

    def cancel_pending(self, run_id: str) -> None:
        now = _now()
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE uploads SET status = ?, error = ?, updated_at = ? "
                "WHERE run_id = ? AND status IN (?, ?)",
                (
                    UploadStatus.FAILED,
                    "run cancelled",
                    now,
                    run_id,
                    UploadStatus.PENDING,
                    UploadStatus.IN_PROGRESS,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def cleanup_resolved(self, max_age_hours: int = 24) -> int:
        cutoff = (
            datetime.now(UTC) - timedelta(hours=max_age_hours)
        ).isoformat()
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM uploads WHERE status IN (?, ?) AND updated_at < ?",
                (UploadStatus.COMPLETED, UploadStatus.FAILED, cutoff),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
