# flake8: noqa: E501
import importlib
import sqlite3
from pathlib import Path

import pytest

from luml.experiments.backends.migration_runner import MetaDBMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker

migration_005 = importlib.import_module(
    "luml.experiments.backends.migrations.005_add_metadata_and_upload_status"
)


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Migration 005 – schema + backfill
# ---------------------------------------------------------------------------


class TestMigration005Schema:
    def test_up_adds_metadata_and_upload_status_columns(self, tmp_path: Path) -> None:
        db_path = tmp_path / "meta.db"
        conn = sqlite3.connect(str(db_path))
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=4)
        assert "metadata" not in _column_names(conn, "experiments")
        assert "upload_status" not in _column_names(conn, "experiments")

        migration_005.up(conn)
        conn.commit()

        cols = _column_names(conn, "experiments")
        assert "metadata" in cols
        assert "upload_status" in cols

    def test_down_drops_metadata_and_upload_status_columns(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "meta.db"
        conn = sqlite3.connect(str(db_path))
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()
        assert "metadata" in _column_names(conn, "experiments")
        assert "upload_status" in _column_names(conn, "experiments")

        migration_005.down(conn)
        conn.commit()

        cols = _column_names(conn, "experiments")
        assert "metadata" not in cols
        assert "upload_status" not in cols


class TestMigration005Backfill:
    def test_pre_existing_rows_backfill_to_unknown(self, tmp_path: Path) -> None:
        db_path = tmp_path / "meta.db"
        conn = sqlite3.connect(str(db_path))
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=4)

        # Need a group first because experiments references experiment_groups
        conn.execute(
            "INSERT INTO experiment_groups (id, name) VALUES (?, ?)",
            ("g1", "legacy-group"),
        )
        conn.execute(
            "INSERT INTO experiments (id, name, group_id) VALUES (?, ?, ?)",
            ("legacy-exp", "legacy", "g1"),
        )
        conn.commit()

        migration_005.up(conn)
        conn.commit()

        row = conn.execute(
            "SELECT upload_status FROM experiments WHERE id = ?", ("legacy-exp",)
        ).fetchone()
        assert row[0] == "unknown"

    def test_backfill_runs_via_full_runner(self, tmp_path: Path) -> None:
        # Same scenario, but driven through the runner.migrate() entrypoint
        # to confirm migration 005 fires correctly in the standard upgrade path.
        db_path = tmp_path / "meta.db"
        conn = sqlite3.connect(str(db_path))
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=4)

        conn.execute(
            "INSERT INTO experiment_groups (id, name) VALUES (?, ?)",
            ("g1", "legacy-group"),
        )
        conn.execute(
            "INSERT INTO experiments (id, name, group_id) VALUES (?, ?, ?)",
            ("legacy-exp", "legacy", "g1"),
        )
        conn.commit()

        applied = runner.migrate()
        assert 5 in applied

        row = conn.execute(
            "SELECT upload_status, metadata FROM experiments WHERE id = ?",
            ("legacy-exp",),
        ).fetchone()
        assert row[0] == "unknown"
        assert row[1] is None


# ---------------------------------------------------------------------------
# ExperimentTracker – new experiment defaults
# ---------------------------------------------------------------------------


class TestNewExperimentDefaults:
    def test_new_experiment_starts_not_uploaded(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="fresh")
        assert tracker.get_experiment_upload_status(exp_id) == "not_uploaded"

    def test_new_experiment_record_reports_not_uploaded(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="fresh")
        exp = tracker.get_experiment_record(exp_id)
        assert exp is not None
        assert exp.upload_status == "not_uploaded"

    def test_new_experiment_metadata_starts_empty(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="fresh")
        assert tracker.get_experiment_metadata(exp_id) == {}

    def test_new_experiment_record_metadata_starts_empty(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="fresh")
        exp = tracker.get_experiment_record(exp_id)
        assert exp is not None
        assert exp.metadata == {}


# ---------------------------------------------------------------------------
# Metadata accessors – arbitrary JSON round-trip
# ---------------------------------------------------------------------------


class TestMetadataRoundTrip:
    def test_set_and_get_simple_dict(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="m1")
        payload = {"foo": "bar", "n": 42}
        tracker.set_experiment_metadata(exp_id, payload)
        assert tracker.get_experiment_metadata(exp_id) == payload

    def test_set_and_get_nested_json(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="m2")
        payload = {
            "mlflow.runName": "happy-cat-42",
            "mlflow.source.git.commit": "abc123",
            "nested": {"a": [1, 2, 3], "b": {"c": True}},
        }
        tracker.set_experiment_metadata(exp_id, payload)
        assert tracker.get_experiment_metadata(exp_id) == payload

    def test_update_merges_keys(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="m3")
        tracker.set_experiment_metadata(exp_id, {"a": 1, "b": 2})
        result = tracker.update_experiment_metadata(exp_id, {"b": 20, "c": 3})
        assert result == {"a": 1, "b": 20, "c": 3}
        assert tracker.get_experiment_metadata(exp_id) == {"a": 1, "b": 20, "c": 3}

    def test_update_with_none_value_removes_key(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="m4")
        tracker.set_experiment_metadata(exp_id, {"keep": "yes", "drop": "no"})
        result = tracker.update_experiment_metadata(exp_id, {"drop": None})
        assert result == {"keep": "yes"}
        assert tracker.get_experiment_metadata(exp_id) == {"keep": "yes"}

    def test_empty_metadata_persists_as_null_column(
        self, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        exp_id = tracker.start_experiment(name="m5")
        tracker.set_experiment_metadata(exp_id, {})
        # Read directly from sqlite to confirm we did not write "{}" or "null"
        conn = sqlite3.connect(str(tmp_path / "experiments" / "meta.db"))
        row = conn.execute(
            "SELECT metadata FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        conn.close()
        assert row[0] is None

    def test_metadata_surfaces_in_experiment_data(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="m6")
        payload = {"mlflow.runName": "abc"}
        tracker.set_experiment_metadata(exp_id, payload)
        data = tracker.get_experiment(exp_id)
        assert data is not None
        assert data.metadata.metadata == payload
        assert data.metadata.upload_status == "not_uploaded"

    def test_get_metadata_on_missing_experiment_raises(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            tracker.get_experiment_metadata("does-not-exist")

    def test_set_metadata_on_missing_experiment_raises(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            tracker.set_experiment_metadata("does-not-exist", {"k": "v"})


# ---------------------------------------------------------------------------
# upload_status accessors
# ---------------------------------------------------------------------------


class TestUploadStatusAccessors:
    @pytest.mark.parametrize(
        "status",
        ["unknown", "not_uploaded", "uploading", "uploaded", "failed"],
    )
    def test_all_legal_statuses_round_trip(
        self, tracker: ExperimentTracker, status: str
    ) -> None:
        exp_id = tracker.start_experiment(name=f"s-{status}")
        tracker.set_experiment_upload_status(exp_id, status)
        assert tracker.get_experiment_upload_status(exp_id) == status

    def test_invalid_status_is_rejected(self, tracker: ExperimentTracker) -> None:
        exp_id = tracker.start_experiment(name="s-bad")
        with pytest.raises(ValueError, match="Invalid upload_status"):
            tracker.set_experiment_upload_status(exp_id, "totally-bogus")

    def test_status_reflected_in_list_experiments(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="s-list")
        tracker.set_experiment_upload_status(exp_id, "uploaded")
        exps = [e for e in tracker.list_experiments() if e.id == exp_id]
        assert len(exps) == 1
        assert exps[0].upload_status == "uploaded"

    def test_get_upload_status_on_missing_experiment_raises(
        self, tracker: ExperimentTracker
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            tracker.get_experiment_upload_status("does-not-exist")


# ---------------------------------------------------------------------------
# Backend-level: lifecycle status is independent from upload_status
# ---------------------------------------------------------------------------


class TestLifecycleStatusUntouched:
    def test_end_experiment_does_not_change_upload_status(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="lifecycle")
        tracker.end_experiment(exp_id)
        # Lifecycle column moves to "completed"; upload_status stays put.
        exp = tracker.get_experiment_record(exp_id)
        assert exp is not None
        assert exp.status == "completed"
        assert exp.upload_status == "not_uploaded"

    def test_setting_upload_status_does_not_change_lifecycle(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="lifecycle2")
        tracker.set_experiment_upload_status(exp_id, "uploaded")
        exp = tracker.get_experiment_record(exp_id)
        assert exp is not None
        assert exp.status == "active"
        assert exp.upload_status == "uploaded"


# ---------------------------------------------------------------------------
# Legacy-row backfill surfaces through the tracker
# ---------------------------------------------------------------------------


class TestLegacyBackfillVisibleViaTracker:
    def test_legacy_experiment_reports_unknown(self, tmp_path: Path) -> None:
        # Build a meta.db at v4, register an experiment, then open the backend
        # — its constructor runs migration 005, which backfills the legacy row.
        base = tmp_path / "experiments"
        base.mkdir()
        meta_path = base / "meta.db"

        conn = sqlite3.connect(str(meta_path))
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=4)
        conn.execute(
            "INSERT INTO experiment_groups (id, name) VALUES (?, ?)",
            ("legacy-group-id", "default"),
        )
        conn.execute(
            "INSERT INTO experiments (id, name, group_id) VALUES (?, ?, ?)",
            ("legacy-exp", "legacy", "legacy-group-id"),
        )
        conn.commit()
        conn.close()

        backend = SQLiteBackend(str(base))
        assert backend.get_experiment_upload_status("legacy-exp") == "unknown"
        exp = backend.get_experiment("legacy-exp")
        assert exp is not None
        assert exp.upload_status == "unknown"
        assert exp.metadata == {}
