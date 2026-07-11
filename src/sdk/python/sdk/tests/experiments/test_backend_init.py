from pathlib import Path

from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker


def test_backend_creates_missing_parent_dirs(tmp_path: Path) -> None:
    base_path = tmp_path / "nested" / "missing" / "experiments"

    backend = SQLiteBackend(str(base_path))

    assert backend.base_path.is_dir()
    assert backend.meta_db_path.exists()


def test_tracker_creates_missing_parent_dirs(tmp_path: Path) -> None:
    base_path = tmp_path / "missing" / "experiments"

    tracker = ExperimentTracker(f"sqlite://{base_path}")
    exp_id = tracker.start_experiment(name="init-test")

    assert base_path.is_dir()
    assert exp_id
