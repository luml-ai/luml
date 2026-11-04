import sqlite3
import threading
from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tracker import ThreadSafeTracker, TrackerProvider


@pytest.fixture
def conn_string(tmp_path: Path) -> str:
    return f"sqlite://{tmp_path / 'experiments'}"


class TestThreadSafeTracker:
    def test_is_experiment_tracker_subclass(self) -> None:
        assert issubclass(ThreadSafeTracker, ExperimentTracker)

    def test_isinstance_check(self, conn_string: str) -> None:
        tracker = ThreadSafeTracker(conn_string)
        assert isinstance(tracker, ExperimentTracker)

    def test_basic_operations(self, conn_string: str) -> None:
        tracker = ThreadSafeTracker(conn_string)
        exp_id = tracker.start_experiment(name="test")
        tracker.log_static("lr", 0.01, experiment_id=exp_id)
        record = tracker.get_experiment_record(exp_id)
        assert record is not None
        assert record.name == "test"
        tracker.end_experiment(exp_id)

    def test_serializes_concurrent_access(self, conn_string: str) -> None:
        tracker = ThreadSafeTracker(conn_string)
        exp_id = tracker.start_experiment(name="concurrent")
        errors: list[Exception] = []
        barrier = threading.Barrier(4)

        def worker(step: int) -> None:
            try:
                barrier.wait(timeout=5)
                tracker.log_static(f"key_{step}", step, experiment_id=exp_id)
                tracker.get_experiment_record(exp_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors
        data = tracker.get_experiment(exp_id)
        assert len(data.static_params) == 4


def test_provider_retries_a_busy_tracker_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "experiments"
    tracker = ThreadSafeTracker(f"sqlite://{store}")
    provider = TrackerProvider(lambda: store)
    attempts = 0

    def flaky(_experiment_id: str) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("database is locked")
        return "record"

    monkeypatch.setattr(tracker, "get_experiment_record", flaky)
    with provider.bind(tracker):
        assert provider.read_experiment("exp-1") == "record"
    assert attempts == 2
