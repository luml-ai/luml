import threading
from pathlib import Path

import pytest

from luml_agent.services.upload_queue import (
    UploadQueue,
    UploadStatus,
)


@pytest.fixture
def queue(tmp_path: Path) -> UploadQueue:
    return UploadQueue(tmp_path / "uploads.db")


@pytest.fixture
def model_file(tmp_path: Path) -> Path:
    f = tmp_path / "model.luml"
    f.write_bytes(b"x" * 1024)
    return f


class TestEnqueue:
    def test_creates_pending_upload(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        assert upload.run_id == "run-1"
        assert upload.node_id == "node-1"
        assert upload.model_path == str(model_file)
        assert upload.experiment_ids == ["exp-1"]
        assert upload.file_size == 1024
        assert upload.status == UploadStatus.PENDING
        assert upload.retry_count == 0

    def test_file_size_zero_when_missing(
        self, queue: UploadQueue,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", "/nonexistent/model.luml", ["exp-1"],
        )
        assert upload.file_size == 0

    def test_multiple_experiment_ids(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file),
            ["exp-1", "exp-2", "exp-3"],
        )
        assert upload.experiment_ids == ["exp-1", "exp-2", "exp-3"]


class TestClaim:
    def test_claim_pending_returns_true(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        assert queue.claim(upload.id) is True
        fetched = queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.IN_PROGRESS

    def test_claim_already_claimed_returns_false(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        assert queue.claim(upload.id) is True
        assert queue.claim(upload.id) is False

    def test_claim_nonexistent_returns_false(
        self, queue: UploadQueue,
    ) -> None:
        assert queue.claim("nonexistent") is False

    def test_claim_is_atomic_concurrent(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        results: list[bool] = []
        lock = threading.Lock()

        def try_claim() -> None:
            result = queue.claim(upload.id)
            with lock:
                results.append(result)

        threads = [threading.Thread(target=try_claim) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(True) == 1
        assert results.count(False) == 4


class TestComplete:
    def test_marks_as_completed(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.claim(upload.id)
        queue.complete(upload.id)
        fetched = queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.COMPLETED


class TestFail:
    def test_first_failure_sets_pending(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.claim(upload.id)
        queue.fail(upload.id, "network error")
        fetched = queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.PENDING
        assert fetched.retry_count == 1
        assert fetched.error == "network error"

    def test_second_failure_still_pending(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.claim(upload.id)
        queue.fail(upload.id, "error 1")
        queue.claim(upload.id)
        queue.fail(upload.id, "error 2")
        fetched = queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.PENDING
        assert fetched.retry_count == 2

    def test_third_failure_sets_failed(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        for i in range(3):
            queue.claim(upload.id)
            queue.fail(upload.id, f"error {i}")
        fetched = queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.FAILED
        assert fetched.retry_count == 3

    def test_fail_nonexistent_is_noop(
        self, queue: UploadQueue,
    ) -> None:
        queue.fail("nonexistent", "error")


class TestGetPending:
    def test_returns_only_pending_for_run(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        u1 = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.enqueue(
            "run-1", "node-2", str(model_file), ["exp-2"],
        )
        queue.enqueue(
            "run-2", "node-3", str(model_file), ["exp-3"],
        )
        queue.claim(u1.id)

        pending = queue.get_pending("run-1")
        assert len(pending) == 1
        assert pending[0].node_id == "node-2"

    def test_returns_empty_when_no_pending(
        self, queue: UploadQueue,
    ) -> None:
        assert queue.get_pending("run-999") == []


class TestCancelPending:
    def test_cancels_pending_and_in_progress(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        u1 = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.enqueue(
            "run-1", "node-2", str(model_file), ["exp-2"],
        )
        queue.claim(u1.id)

        queue.cancel_pending("run-1")

        for uid in [u1.id]:
            fetched = queue.get(uid)
            assert fetched is not None
            assert fetched.status == UploadStatus.FAILED
            assert fetched.error == "run cancelled"

    def test_does_not_cancel_other_runs(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        u2 = queue.enqueue(
            "run-2", "node-2", str(model_file), ["exp-2"],
        )
        queue.cancel_pending("run-1")

        fetched = queue.get(u2.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.PENDING


class TestCleanupResolved:
    def test_removes_old_completed_and_failed(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        u1 = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.claim(u1.id)
        queue.complete(u1.id)

        removed = queue.cleanup_resolved(max_age_hours=0)
        assert removed == 1
        assert queue.get(u1.id) is None

    def test_preserves_recent_entries(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        u1 = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.claim(u1.id)
        queue.complete(u1.id)

        removed = queue.cleanup_resolved(max_age_hours=24)
        assert removed == 0
        assert queue.get(u1.id) is not None

    def test_preserves_pending(
        self, queue: UploadQueue, model_file: Path,
    ) -> None:
        queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        removed = queue.cleanup_resolved(max_age_hours=0)
        assert removed == 0
