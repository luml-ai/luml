from pathlib import Path
from unittest.mock import MagicMock

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


# --- Hook mechanism ---


class TestPreEndHooks:
    def test_hook_called_on_end_experiment(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        hook = MagicMock()
        tracker.add_pre_end_hook(hook)
        tracker.end_experiment(exp_id)
        hook.assert_called_once()

    def test_hook_called_before_backend_end(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        call_order: list[str] = []
        tracker.add_pre_end_hook(lambda: call_order.append("hook"))
        original_end = tracker.backend.end_experiment

        def tracking_end(eid: str) -> None:
            call_order.append("backend")
            original_end(eid)

        tracker.backend.end_experiment = tracking_end  # type: ignore[assignment]
        tracker.end_experiment(exp_id)
        assert call_order == ["hook", "backend"]

    def test_multiple_hooks_called_in_order(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        order: list[int] = []
        tracker.add_pre_end_hook(lambda: order.append(1))
        tracker.add_pre_end_hook(lambda: order.append(2))
        tracker.add_pre_end_hook(lambda: order.append(3))
        tracker.end_experiment(exp_id)
        assert order == [1, 2, 3]

    def test_hook_exception_doesnt_prevent_end(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        def bad_hook() -> None:
            raise RuntimeError("hook failed")

        tracker.add_pre_end_hook(bad_hook)
        tracker.end_experiment(exp_id)
        assert tracker.current_experiment_id is None

    def test_no_hooks_registered(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.end_experiment(exp_id)
        assert tracker.current_experiment_id is None


# --- TracerManager.flush ---


class TestTracerManagerFlush:
    def test_flush_delegates_to_provider(self) -> None:
        mock_provider = MagicMock()
        mock_provider.force_flush.return_value = True
        original = TracerManager._provider
        try:
            TracerManager._provider = mock_provider
            result = TracerManager.flush(timeout_millis=5000)
            mock_provider.force_flush.assert_called_once_with(5000)
            assert result is True
        finally:
            TracerManager._provider = original

    def test_flush_returns_true_when_no_provider(self) -> None:
        original = TracerManager._provider
        try:
            TracerManager._provider = None
            assert TracerManager.flush() is True
        finally:
            TracerManager._provider = original

    def test_flush_returns_provider_result(self) -> None:
        mock_provider = MagicMock()
        mock_provider.force_flush.return_value = False
        original = TracerManager._provider
        try:
            TracerManager._provider = mock_provider
            assert TracerManager.flush() is False
        finally:
            TracerManager._provider = original


# --- set_experiment_tracker wiring ---


class TestSetExperimentTracker:
    def test_registers_flush_hook(self, tracker: ExperimentTracker) -> None:
        TracerManager.set_experiment_tracker(tracker)
        assert TracerManager.flush in tracker._pre_end_hooks

    def test_rejects_non_tracker(self) -> None:
        with pytest.raises(
            ValueError, match="must be an instance of ExperimentTracker"
        ):
            TracerManager.set_experiment_tracker("not a tracker")  # type: ignore[arg-type]


# --- Integration: multi-threaded span export ---


class TestMultiThreadedSpanExport:
    def test_spans_from_multiple_threads_flushed_before_end(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        mock_provider = MagicMock()
        mock_provider.force_flush.return_value = True
        original = TracerManager._provider
        try:
            TracerManager._provider = mock_provider
            TracerManager.set_experiment_tracker(tracker)

            tracker.end_experiment(exp_id)

            mock_provider.force_flush.assert_called_once()
        finally:
            TracerManager._provider = original

    def test_flush_called_before_backend_end_in_integration(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        call_order: list[str] = []

        mock_provider = MagicMock()

        def track_flush(timeout: int = 30000) -> bool:
            call_order.append("flush")
            return True

        mock_provider.force_flush.side_effect = track_flush

        original_end = tracker.backend.end_experiment

        def track_end(eid: str) -> None:
            call_order.append("backend_end")
            original_end(eid)

        tracker.backend.end_experiment = track_end  # type: ignore[assignment]

        original = TracerManager._provider
        try:
            TracerManager._provider = mock_provider
            TracerManager.set_experiment_tracker(tracker)
            tracker.end_experiment(exp_id)
            assert call_order == ["flush", "backend_end"]
        finally:
            TracerManager._provider = original

    def test_tracker_reuse_across_experiments(self, tracker: ExperimentTracker) -> None:
        mock_provider = MagicMock()
        mock_provider.force_flush.return_value = True
        original = TracerManager._provider
        try:
            TracerManager._provider = mock_provider
            TracerManager.set_experiment_tracker(tracker)

            for run in range(2):
                exp_id = tracker.start_experiment(name=f"run-{run}")
                tracker.end_experiment(exp_id)

            assert mock_provider.force_flush.call_count == 2
        finally:
            TracerManager._provider = original

    def test_flush_hook_survives_provider_flush_error(
        self, tracker: ExperimentTracker
    ) -> None:
        mock_provider = MagicMock()
        mock_provider.force_flush.side_effect = RuntimeError("flush failed")
        original = TracerManager._provider
        try:
            TracerManager._provider = mock_provider
            TracerManager.set_experiment_tracker(tracker)

            exp_id = tracker.start_experiment(name="test")
            tracker.end_experiment(exp_id)
            assert tracker.current_experiment_id is None
        finally:
            TracerManager._provider = original
