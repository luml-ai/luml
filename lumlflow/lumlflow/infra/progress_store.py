import json
import threading
import time
from dataclasses import dataclass, field
from typing import Literal

from luml.api.utils.progress import BaseProgressHandler

_JOB_TTL_SECONDS = 60 * 10


@dataclass
class UploadJob:
    status: Literal["running", "complete", "error"]
    percent: int = 0
    result: list | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.monotonic)

    def to_json(self) -> str:
        if self.status == "complete":
            return json.dumps({"type": "complete", "artifacts": self.result})
        if self.status == "error":
            return json.dumps({"type": "error", "message": self.error})
        return json.dumps({"type": "progress", "percent": self.percent})


class ProgressStore:
    def __init__(self) -> None:
        self._jobs: dict[str, UploadJob] = {}
        self._lock = threading.Lock()

    def _evict_stale(self) -> None:
        cutoff = time.monotonic() - _JOB_TTL_SECONDS
        stale = [jid for jid, job in self._jobs.items() if job.created_at < cutoff]
        for jid in stale:
            del self._jobs[jid]

    def create(self, job_id: str) -> None:
        with self._lock:
            self._evict_stale()
            self._jobs[job_id] = UploadJob(status="running")

    def update_progress(self, job_id: str, percent: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.percent = max(0, min(100, percent))

    def set_complete(self, job_id: str, result: list) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "complete"
            job.result = result
            job.percent = 100

    def set_error(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "error"
            job.error = message

    def get(self, job_id: str) -> UploadJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def make_handler(
        self, job_id: str, item_idx: int = 0, total_items: int = 1
    ) -> "SSEProgressHandler":
        return SSEProgressHandler(self, job_id, item_idx, total_items)

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)


class SSEProgressHandler(BaseProgressHandler):
    def __init__(
        self,
        store: ProgressStore,
        job_id: str,
        item_idx: int = 0,
        total_items: int = 1,
    ) -> None:
        self._store = store
        self._job_id = job_id
        self._item_idx = item_idx
        self._total_items = total_items

    def on_chunk(self, uploaded: int, total: int) -> None:
        if total > 0:
            item_progress = uploaded / total
        else:
            item_progress = 0
        percent = int((self._item_idx + item_progress) / self._total_items * 100)
        self._store.update_progress(self._job_id, percent)

    def finish(self) -> None:
        pass
