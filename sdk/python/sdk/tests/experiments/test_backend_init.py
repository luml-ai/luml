from pathlib import Path

import pytest

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


@pytest.mark.parametrize("status", ["active", "completed", "error"])
def test_backend_rejects_existing_id_after_reopening(
    tmp_path: Path, dummy_model_file: Path, status: str
) -> None:
    base_path = tmp_path / "experiments"
    backend = SQLiteBackend(str(base_path))
    backend.initialize_experiment(
        "exp-1",
        name="original",
        group="training",
        tags=["v1"],
        description="original description",
        source="train.py",
    )
    backend.log_model("exp-1", str(dummy_model_file), name="baseline")
    if status == "completed":
        backend.end_experiment("exp-1")
    elif status == "error":
        backend.fail_experiment("exp-1")
    before = backend.get_experiment("exp-1")

    reopened = SQLiteBackend(str(base_path))
    with pytest.raises(ValueError, match="Experiment 'exp-1' already exists"):
        reopened.initialize_experiment("exp-1")

    assert reopened.get_experiment("exp-1") == before
