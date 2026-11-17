import math
import sqlite3
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.tracker import ExperimentTracker
from lumlflow.service import AppService

Point = tuple[int, float]

LEGACY_INSERT = (
    "INSERT INTO dynamic_metrics (key, value, step, logged_at) VALUES (?, ?, ?, ?)"
)


def log_points(
    tracker: ExperimentTracker, experiment_id: str, key: str, points: list[Point]
) -> None:
    for step, value in points:
        tracker.log_dynamic(key, value, step=step, experiment_id=experiment_id)


def serve(tracker: ExperimentTracker) -> TestClient:
    with patch("lumlflow.api.experiments.ExperimentsHandler.__init__", lambda _: None):
        app = AppService()
    from lumlflow.api.experiments import experiments_handler

    experiments_handler.tracker = tracker
    return TestClient(
        app, headers={"Authorization": f"Bearer {app.state.session_token}"}
    )


def require_newer_reader(db_path: Path) -> None:
    """Marks the database as a revision 4 that this SDK must refuse to read."""
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exp_schema_migrations (version) VALUES (4)")
    conn.execute(
        "UPDATE exp_schema_info SET value = '4' WHERE key = 'min_reader_revision'"
    )
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()


def revision2_experiment(
    store: Path, key: str, points: list[Point]
) -> tuple[str, Path]:
    """An experiment whose database is what released SDKs write: revision 2."""
    setup = ExperimentTracker(f"sqlite://{store}")
    experiment_id = setup.start_experiment(name="released")
    setup.end_experiment(experiment_id)
    setup.backend.close()
    db_path = store / experiment_id / "exp.db"
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    ExperimentMigrationRunner(conn).migrate(target_version=2)
    conn.executemany(
        LEGACY_INSERT,
        [
            (key, None if math.isnan(value) else value, step, "2026-01-02 03:04:05")
            for step, value in points
        ],
    )
    conn.commit()
    conn.close()
    return experiment_id, db_path
