import io
import sqlite3
import tarfile
from pathlib import Path

import pytest

from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def tracker_with_experiment(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="scenario_exp")
    return tracker, exp_id


@pytest.fixture
def dummy_model_file(tmp_path: Path) -> Path:
    model_path = tmp_path / "dummy_model.luml"
    with tarfile.open(model_path, "w") as tar:
        data = b"fake model weights"
        info = tarfile.TarInfo(name="model.bin")
        info.size = len(data)
        tar.addfile(info, fileobj=io.BytesIO(data))
    return model_path


@pytest.fixture
def backend(tmp_path: Path) -> SQLiteBackend:
    return SQLiteBackend(str(tmp_path / "experiments"))


@pytest.fixture
def backend_with_experiment(
    tmp_path: Path,
) -> tuple[SQLiteBackend, str]:
    backend = SQLiteBackend(str(tmp_path / "experiments"))
    exp_id = "test-exp-id"
    backend.initialize_experiment(exp_id, "default", "test")
    return backend, exp_id


def _exp_db(tmp_path: Path, exp_id: str) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "experiments" / exp_id / "exp.db")


def _meta_db(tmp_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(tmp_path / "experiments" / "meta.db")
