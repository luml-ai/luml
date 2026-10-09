import sqlite3
from pathlib import Path

from luml.experiments.backends.migration_runner import MetaDBMigrationRunner
from luml.experiments.tracker import ExperimentTracker


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


class TestRemoteArtifacts:
    def test_mapping_is_upserted_and_scoped_to_orbit(
        self, tracker: ExperimentTracker
    ) -> None:
        tracker.set_remote_artifact("experiment", "L", "orbit-1", "a1")
        tracker.set_remote_artifact("experiment", "L", "orbit-1", "a2")

        assert tracker.get_remote_artifact("experiment", "L", "orbit-1") == "a2"
        assert tracker.get_remote_artifact("experiment", "L", "orbit-2") is None

    def test_mapping_is_scoped_to_local_type(self, tracker: ExperimentTracker) -> None:
        tracker.set_remote_artifact("experiment", "L", "orbit-1", "experiment-a")
        tracker.set_remote_artifact("model", "L", "orbit-1", "model-a")

        assert (
            tracker.get_remote_artifact("experiment", "L", "orbit-1") == "experiment-a"
        )
        assert tracker.get_remote_artifact("model", "L", "orbit-1") == "model-a"

    def test_delete_is_idempotent(self, tracker: ExperimentTracker) -> None:
        tracker.set_remote_artifact("experiment", "L", "orbit-1", "a1")

        tracker.delete_remote_artifact("experiment", "L", "orbit-1")
        tracker.delete_remote_artifact("experiment", "L", "orbit-1")

        assert tracker.get_remote_artifact("experiment", "L", "orbit-1") is None


class TestRemoteArtifactsMigration:
    def test_rollback_removes_table_and_restores_version_5(
        self, tmp_path: Path
    ) -> None:
        conn = sqlite3.connect(tmp_path / "meta.db")
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()

        assert runner.get_current_version() == 6
        assert _table_exists(conn, "remote_artifacts")

        assert runner.rollback(target_version=5) == [6]
        assert runner.get_current_version() == 5
        assert not _table_exists(conn, "remote_artifacts")
