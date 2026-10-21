import gc
import sqlite3
import subprocess
import sys
import weakref
from pathlib import Path

import pytest

from luml.experiments.backends.sqlite import ConnectionPool, SQLiteBackend
from luml.experiments.tracker import ExperimentTracker


def test_connection_pool_is_collectable() -> None:
    pool = ConnectionPool()
    pool_ref = weakref.ref(pool)

    del pool
    gc.collect()

    assert pool_ref() is None


def test_backend_collection_closes_connections(tmp_path: Path) -> None:
    backend = SQLiteBackend(str(tmp_path))
    backend.initialize_experiment("exp")
    with (
        backend.pool.get_connection(backend.meta_db_path) as meta_connection,
        backend.pool.get_connection(tmp_path / "exp" / "exp.db") as exp_connection,
    ):
        connections = [meta_connection, exp_connection]
    backend_ref = weakref.ref(backend)
    pool_ref = weakref.ref(backend.pool)

    del backend
    gc.collect()

    assert backend_ref() is None
    assert pool_ref() is None
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connection.execute("SELECT 1")


@pytest.mark.parametrize("active", [False, True])
def test_tracker_and_backend_are_collectable(tmp_path: Path, active: bool) -> None:
    tracker = ExperimentTracker(f"sqlite://{tmp_path}")
    if active:
        tracker.start_experiment(experiment_id="exp")
    tracker_ref = weakref.ref(tracker)
    backend_ref = weakref.ref(tracker.backend)

    del tracker
    gc.collect()

    assert tracker_ref() is None
    assert backend_ref() is None


@pytest.mark.parametrize("completed", [False, True])
def test_tracker_exit_cleanup_preserves_experiment_status(
    tmp_path: Path, completed: bool
) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from luml.experiments.tracker import ExperimentTracker\n"
            "import sys\n"
            "tracker = ExperimentTracker(f'sqlite://{sys.argv[1]}')\n"
            "tracker.start_experiment(experiment_id='exp')\n"
            "if sys.argv[2] == 'True':\n"
            "    tracker.end_experiment()\n",
            str(tmp_path),
            str(completed),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    with sqlite3.connect(tmp_path / "meta.db") as connection:
        status = connection.execute(
            "SELECT status FROM experiments WHERE id = 'exp'"
        ).fetchone()[0]

    assert status == ("completed" if completed else "error")


def test_dropped_tracker_fails_its_active_experiment(tmp_path: Path) -> None:
    tracker = ExperimentTracker(f"sqlite://{tmp_path}")
    tracker.start_experiment(experiment_id="exp")
    backend = tracker.backend

    del tracker
    gc.collect()

    assert backend.get_experiment("exp").status == "error"


def test_dropped_tracker_leaves_finished_experiment_alone(tmp_path: Path) -> None:
    tracker = ExperimentTracker(f"sqlite://{tmp_path}")
    tracker.start_experiment(experiment_id="exp")
    tracker.end_experiment()
    backend = tracker.backend

    del tracker
    gc.collect()

    assert backend.get_experiment("exp").status == "completed"
