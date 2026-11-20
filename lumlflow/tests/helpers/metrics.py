import json
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
    """Marks the database as a revision 5 that this SDK must refuse to read."""
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exp_schema_migrations (version) VALUES (5)")
    conn.execute(
        "UPDATE exp_schema_info SET value = '5' WHERE key = 'min_reader_revision'"
    )
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    conn.close()


# What SDK releases before the migration runner created.
REVISION0_DDL = """
CREATE TABLE dynamic_metrics (
    key TEXT,
    value REAL,
    step INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (key, step)
);
CREATE INDEX idx_dynamic_metrics_key_step ON dynamic_metrics (key, step);
"""


def revision2_experiment(
    store: Path, key: str, points: list[Point], *, revision: int = 2
) -> tuple[str, Path]:
    """An experiment whose database is what released SDKs write: revision 2,
    or the older `revision` 0 or 1."""
    setup = ExperimentTracker(f"sqlite://{store}")
    experiment_id = setup.start_experiment(name="released")
    setup.end_experiment(experiment_id)
    setup.backend.close()
    db_path = store / experiment_id / "exp.db"
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    if revision == 0:
        conn.executescript(REVISION0_DDL)
    else:
        ExperimentMigrationRunner(conn).migrate(target_version=revision)
    conn.executemany(
        LEGACY_INSERT,
        [
            (key, None if math.isnan(value) else value, step, "2026-01-02 03:04:05")
            for step, value in points
        ],
    )
    conn.commit()
    conn.close()
    # Released SDKs list the logged metrics on the experiment row when it ends.
    if points:
        meta = sqlite3.connect(store / "meta.db")
        meta.execute(
            "UPDATE experiments SET dynamic_params = ? WHERE id = ?",
            (json.dumps({key: max(points)[1]}), experiment_id),
        )
        meta.commit()
        meta.close()
    return experiment_id, db_path
