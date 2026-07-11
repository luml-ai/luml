from pathlib import Path

import pytest

from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def backend(tmp_path: Path) -> SQLiteBackend:
    return SQLiteBackend(str(tmp_path / "experiments"))


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


def test_fresh_experiment_has_current_ddl_version(backend: SQLiteBackend) -> None:
    exp_id = "version-test"
    backend.initialize_experiment(exp_id, "default", "test")
    assert backend.get_experiment_ddl_version(exp_id)


def test_tracker_get_experiment_ddl_version(tracker: ExperimentTracker) -> None:
    exp_id = tracker.start_experiment(name="version-test")
    assert tracker.get_experiment_ddl_version(exp_id)
