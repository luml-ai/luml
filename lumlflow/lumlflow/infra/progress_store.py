import json
import threading
from dataclasses import dataclass
from typing import Literal


@dataclass
class UploadJob:
    status: Literal["running", "complete", "error"]
    percent: int = 0
    uploaded_bytes: int = 0
    total_bytes: int = 0
    result: list | None = None
    error: str | None = None

    def to_json(self) -> str:
        if self.status == "complete":
            return json.dumps({"type": "complete", "artifacts": self.result})
        if self.status == "error":
            return json.dumps({"type": "error", "message": self.error})
        return json.dumps(
            {
                "type": "progress",
                "percent": self.percent,
                "uploaded_bytes": self.uploaded_bytes,
                "total_bytes": self.total_bytes,
            }
        )


class ProgressStore:
    def __init__(self) -> None:
        self._jobs: dict[str, UploadJob] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str) -> None:
        with self._lock:
            self._jobs[job_id] = UploadJob(status="running")

    def update_progress(self, job_id: str, uploaded: int, total: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.uploaded_bytes = uploaded
            job.total_bytes = total
            job.percent = int(uploaded / total * 100) if total > 0 else 0

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

    def make_callback(self, job_id: str, item_idx: int = 0, total_items: int = 1):
        def callback(uploaded: int, total: int) -> None:
            if total > 0:
                overall = int((item_idx + uploaded / total) * 100)
            else:
                overall = item_idx * 100
            self.update_progress(job_id, overall, total_items * 100)

        return callback

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)


progress_store = ProgressStore()
