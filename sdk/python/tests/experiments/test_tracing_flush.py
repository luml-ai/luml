import threading
from pathlib import Path

import pytest

from luml.experiments.tracing import TracerManager
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def tracker_with_experiment(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="test_exp")
    return tracker, exp_id


class TestSetExperimentTracker:
    def test_sets_log_fn(self, tracker: ExperimentTracker) -> None:
        TracerManager.set_experiment_tracker(tracker)
        assert TracerManager._log_fn is not None
        assert TracerManager._log_fn.__func__ is ExperimentTracker.log_span  # type: ignore[attr-defined]
        assert TracerManager._log_fn.__self__ is tracker  # type: ignore[attr-defined]

    def test_rejects_non_tracker(self) -> None:
        with pytest.raises(
            ValueError, match="must be an instance of ExperimentTracker"
        ):
            TracerManager.set_experiment_tracker("not a tracker")  # type: ignore[arg-type]


class TestConcurrentWrites:
    def test_concurrent_log_span_no_errors(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        errors: list[Exception] = []
        num_threads = 8
        spans_per_thread = 20
        barrier = threading.Barrier(num_threads)

        def write_spans(thread_id: int) -> None:
            barrier.wait()
            for i in range(spans_per_thread):
                try:
                    tracker.log_span(
                        trace_id=f"trace-{thread_id}",
                        span_id=f"span-{thread_id}-{i}",
                        name=f"op-{thread_id}-{i}",
                        start_time_unix_nano=1000,
                        end_time_unix_nano=2000,
                    )
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=write_spans, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Got {len(errors)} errors: {errors[:3]}"

    def test_concurrent_log_span_and_eval_no_errors(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        errors: list[Exception] = []
        barrier = threading.Barrier(2)

        def write_spans() -> None:
            barrier.wait()
            for i in range(50):
                try:
                    tracker.log_span(
                        trace_id=f"trace-{i}",
                        span_id=f"span-{i}",
                        name=f"op-{i}",
                        start_time_unix_nano=1000,
                        end_time_unix_nano=2000,
                    )
                except Exception as e:
                    errors.append(e)

        def write_evals() -> None:
            barrier.wait()
            for i in range(50):
                try:
                    tracker.log_eval_sample(
                        eval_id=f"eval-{i}",
                        dataset_id="ds1",
                        inputs={"x": i},
                        outputs={"y": i * 2},
                    )
                except Exception as e:
                    errors.append(e)

        t1 = threading.Thread(target=write_spans)
        t2 = threading.Thread(target=write_evals)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors, f"Got {len(errors)} errors: {errors[:3]}"

    def test_all_spans_persisted_under_contention(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        num_threads = 8
        spans_per_thread = 20
        barrier = threading.Barrier(num_threads)

        def write_spans(thread_id: int) -> None:
            barrier.wait()
            for i in range(spans_per_thread):
                tracker.log_span(
                    trace_id=f"trace-{thread_id}",
                    span_id=f"span-{thread_id}-{i}",
                    name=f"op-{thread_id}-{i}",
                    start_time_unix_nano=1000,
                    end_time_unix_nano=2000,
                )

        threads = [
            threading.Thread(target=write_spans, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        conn = tracker.backend._get_experiment_connection(exp_id)  # type: ignore[attr-defined]
        count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        assert count == num_threads * spans_per_thread
