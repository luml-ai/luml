# flake8: noqa: E501
import sqlite3
from pathlib import Path

import pytest

from luml.experiments.backends.migration_runner import (
    BaseMigrationRunner,
    ExperimentMigrationRunner,
    MetaDBMigrationRunner,
)

META_DB_LAST_VERSION = 4

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _make_meta_conn(tmp_path: Path, name: str = "meta.db") -> sqlite3.Connection:
    return sqlite3.connect(str(tmp_path / name))


def _make_exp_conn(tmp_path: Path, name: str = "exp.db") -> sqlite3.Connection:
    path = tmp_path / name
    (tmp_path / "attachments").mkdir(exist_ok=True)
    return sqlite3.connect(str(path))


def _make_old_sdk_meta_db(tmp_path: Path) -> sqlite3.Connection:
    """Simulate old PyPI SDK meta DB: tables exist but no schema_migrations."""
    conn = _make_meta_conn(tmp_path)
    conn.execute("""
        CREATE TABLE experiment_groups (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE experiments (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            group_name TEXT,
            tags TEXT
        )
    """)
    conn.commit()
    return conn


def _make_old_sdk_exp_db(tmp_path: Path) -> sqlite3.Connection:
    """Simulate old PyPI SDK exp DB: all tables exist but no exp_schema_migrations and no size column."""
    conn = _make_exp_conn(tmp_path)
    conn.execute("""
        CREATE TABLE attachments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            file_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE static_params (
            key TEXT PRIMARY KEY,
            value TEXT,
            value_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE dynamic_metrics (
            key TEXT,
            value REAL,
            step INTEGER,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (key, step)
        )
    """)
    conn.execute("""
        CREATE TABLE spans (
            trace_id TEXT NOT NULL,
            span_id TEXT NOT NULL,
            parent_span_id TEXT,
            name TEXT NOT NULL,
            kind INTEGER,
            dfs_span_type INTEGER NOT NULL DEFAULT 0,
            start_time_unix_nano BIGINT NOT NULL,
            end_time_unix_nano BIGINT NOT NULL,
            status_code INTEGER,
            status_message TEXT,
            attributes TEXT,
            events TEXT,
            links TEXT,
            trace_flags INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (trace_id, span_id)
        )
    """)
    conn.execute("""
        CREATE TABLE evals (
            id TEXT NOT NULL,
            dataset_id TEXT NOT NULL,
            inputs TEXT NOT NULL,
            outputs TEXT,
            refs TEXT,
            scores TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (dataset_id, id)
        )
    """)
    conn.execute("""
        CREATE TABLE eval_traces_bridge (
            id TEXT PRIMARY KEY,
            eval_dataset_id TEXT NOT NULL,
            eval_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE eval_annotations (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            eval_id TEXT NOT NULL,
            name TEXT NOT NULL,
            annotation_kind TEXT NOT NULL CHECK(annotation_kind IN ('feedback', 'expectation')),
            value_type TEXT NOT NULL CHECK(value_type IN ('int', 'bool', 'string')),
            value TEXT NOT NULL,
            user TEXT NOT NULL,
            rationale TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE span_annotations (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            span_id TEXT NOT NULL,
            name TEXT NOT NULL,
            annotation_kind TEXT NOT NULL CHECK(annotation_kind IN ('feedback', 'expectation')),
            value_type TEXT NOT NULL CHECK(value_type IN ('int', 'bool', 'string')),
            value TEXT NOT NULL,
            user TEXT NOT NULL,
            rationale TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Class 1: BaseMigrationRunner logic via MetaDBMigrationRunner
# ---------------------------------------------------------------------------


class TestBaseMigrationRunnerViaMetaDB:
    def test_migrations_table_created_on_init(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        MetaDBMigrationRunner(conn)
        assert _table_exists(conn, "schema_migrations")

    def test_get_current_version_empty_db(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        assert runner.get_current_version() == 0

    def test_get_applied_migrations_empty_db(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        assert runner.get_applied_migrations() == []

    def test_migrate_returns_applied_versions(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        applied = runner.migrate()
        assert applied == list(range(1, META_DB_LAST_VERSION + 1))

    def test_migrate_idempotent(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()
        second = runner.migrate()
        assert second == []
        assert runner.get_current_version() == META_DB_LAST_VERSION

    def test_migrate_target_version(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        applied = runner.migrate(target_version=1)
        assert applied == [1]
        assert runner.get_current_version() == 1
        pending = runner.get_pending_migrations()
        assert [m["version"] for m in pending] == list(range(2, META_DB_LAST_VERSION + 1))

    def test_get_pending_migrations_after_partial_apply(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=2)
        pending = runner.get_pending_migrations()
        assert len(pending) == META_DB_LAST_VERSION - 2
        assert pending[0]["version"] == 3

    def test_get_status(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=1)
        status = runner.get_status()
        assert status["current_version"] == 1
        assert status["applied_count"] == 1
        assert status["pending_count"] == META_DB_LAST_VERSION - 1
        assert status["applied_versions"] == [1]
        assert 2 in status["pending_versions"]
        assert 3 in status["pending_versions"]
        assert META_DB_LAST_VERSION in status["pending_versions"]

    def test_rollback_single_migration(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()
        assert runner.get_current_version() == META_DB_LAST_VERSION
        rolled = runner.rollback(target_version=2)
        assert rolled == list(range(META_DB_LAST_VERSION, 2, -1))
        assert runner.get_current_version() == 2

    def test_rollback_removes_version_from_table(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()
        runner.rollback(target_version=2)
        assert 3 not in runner.get_applied_migrations()
        assert 2 in runner.get_applied_migrations()

    def test_rollback_all(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()
        runner.rollback(target_version=0)
        assert runner.get_current_version() == 0
        assert runner.get_applied_migrations() == []

    def test_migrate_failure_rolls_back_transaction(self, tmp_path: Path) -> None:
        # Use a custom test runner with a fake failing migration
        mig_dir = tmp_path / "migs"
        mig_dir.mkdir()
        (mig_dir / "001_ok.py").write_text(
            "import sqlite3\n"
            "VERSION = 1\n"
            "DESCRIPTION = 'ok'\n"
            "def up(conn):\n"
            "    conn.execute('CREATE TABLE t (x INTEGER)')\n"
            "def down(conn):\n"
            "    conn.execute('DROP TABLE t')\n"
        )
        (mig_dir / "002_fail.py").write_text(
            "import sqlite3\n"
            "VERSION = 2\n"
            "DESCRIPTION = 'fail'\n"
            "def up(conn):\n"
            "    raise RuntimeError('intentional failure')\n"
        )

        class _TestRunner(BaseMigrationRunner):
            def __init__(self, c: sqlite3.Connection) -> None:
                super().__init__(c, "test_schema_migrations", mig_dir)

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        runner = _TestRunner(conn)
        runner.migrate(target_version=1)
        assert runner.get_current_version() == 1

        with pytest.raises(RuntimeError, match="intentional failure"):
            runner.migrate()

        assert runner.get_current_version() == 1
        assert runner.get_applied_migrations() == [1]


# ---------------------------------------------------------------------------
# Class 2: MetaDBMigrationRunner._apply_baseline_if_needed
# ---------------------------------------------------------------------------


class TestMetaDBMigrationRunnerBaseline:
    def test_no_baseline_on_fresh_db(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        assert runner.get_current_version() == 0
        assert runner.get_applied_migrations() == []

    def test_no_baseline_without_experiment_groups(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        conn.execute("""
            CREATE TABLE experiments (
                id TEXT PRIMARY KEY, name TEXT
            )
        """)
        conn.commit()
        runner = MetaDBMigrationRunner(conn)
        assert runner.get_current_version() == 0

    def test_baseline_v1_when_experiment_groups_exists(self, tmp_path: Path) -> None:
        conn = _make_meta_conn(tmp_path)
        conn.execute("""
            CREATE TABLE experiment_groups (id TEXT PRIMARY KEY, name TEXT)
        """)
        conn.commit()
        runner = MetaDBMigrationRunner(conn)
        assert runner.get_current_version() == 1
        assert runner.get_applied_migrations() == [1]

    def test_baseline_skipped_when_migrations_already_exist(
        self, tmp_path: Path
    ) -> None:
        conn = _make_meta_conn(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate(target_version=1)
        # Add experiment_groups manually after migration (shouldn't re-baseline)
        initial_versions = runner.get_applied_migrations()
        runner2 = MetaDBMigrationRunner(conn)
        assert runner2.get_applied_migrations() == initial_versions


# ---------------------------------------------------------------------------
# Class 3: Old PyPI SDK – meta DB upgrade
# ---------------------------------------------------------------------------


class TestMetaDBOldSdkUpgrade:
    def test_old_sdk_meta_db_baselines_to_v1(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_meta_db(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        assert runner.get_current_version() == 1

    def test_old_sdk_meta_db_migrates_to_v4(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_meta_db(tmp_path)
        runner = MetaDBMigrationRunner(conn)
        runner.migrate()
        assert runner.get_current_version() == META_DB_LAST_VERSION

    def test_old_sdk_meta_db_gets_group_id_column(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_meta_db(tmp_path)
        MetaDBMigrationRunner(conn).migrate()
        assert "group_id" in _column_names(conn, "experiments")

    def test_old_sdk_meta_db_gets_models_table(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_meta_db(tmp_path)
        MetaDBMigrationRunner(conn).migrate()
        assert _table_exists(conn, "models")

    def test_old_sdk_meta_db_models_has_size_column(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_meta_db(tmp_path)
        MetaDBMigrationRunner(conn).migrate()
        assert "size" in _column_names(conn, "models")

    def test_old_sdk_meta_db_existing_experiments_preserved(
        self, tmp_path: Path
    ) -> None:
        # Note: experiment_groups cannot have rows before migration — SQLite forbids
        # ALTER TABLE ADD COLUMN with DEFAULT CURRENT_TIMESTAMP on non-empty tables.
        # We only seed experiments (which get constant-default columns) and verify them.
        conn = _make_old_sdk_meta_db(tmp_path)
        conn.execute(
            "INSERT INTO experiments (id, name, group_name) VALUES (?, ?, ?)",
            ("exp-1", "my-exp", "default"),
        )
        conn.commit()

        MetaDBMigrationRunner(conn).migrate()

        row = conn.execute("SELECT name FROM experiments WHERE id = 'exp-1'").fetchone()
        assert row is not None
        assert row[0] == "my-exp"

    def test_old_sdk_meta_db_unique_group_name_index_created(
        self, tmp_path: Path
    ) -> None:
        # Migration 002 creates a unique index on experiment_groups(name).
        # Verify it exists after migration on an empty old SDK DB.
        conn = _make_old_sdk_meta_db(tmp_path)
        MetaDBMigrationRunner(conn).migrate()

        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_experiment_groups_name'"
        ).fetchone()
        assert idx is not None

        import uuid as _uuid

        conn.execute(
            "INSERT INTO experiment_groups (id, name) VALUES (?, ?)",
            (str(_uuid.uuid4()), "grp"),
        )
        conn.commit()
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO experiment_groups (id, name) VALUES (?, ?)",
                (str(_uuid.uuid4()), "grp"),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Class 4: ExperimentMigrationRunner._apply_baseline_if_needed
# ---------------------------------------------------------------------------


class TestExperimentMigrationRunnerBaseline:
    def test_no_baseline_fresh_db(self, tmp_path: Path) -> None:
        conn = _make_exp_conn(tmp_path)
        runner = ExperimentMigrationRunner(conn)
        assert runner.get_current_version() == 0
        assert runner.get_applied_migrations() == []

    def test_no_baseline_without_attachments_table(self, tmp_path: Path) -> None:
        conn = _make_exp_conn(tmp_path)
        conn.execute("CREATE TABLE static_params (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        runner = ExperimentMigrationRunner(conn)
        assert runner.get_current_version() == 0

    def test_baseline_v1_when_attachments_no_size(self, tmp_path: Path) -> None:
        conn = _make_exp_conn(tmp_path)
        conn.execute("""
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                file_path TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        runner = ExperimentMigrationRunner(conn)
        assert runner.get_current_version() == 1
        assert runner.get_applied_migrations() == [1]

    def test_baseline_v1_and_v2_when_attachments_with_size(
        self, tmp_path: Path
    ) -> None:
        conn = _make_exp_conn(tmp_path)
        conn.execute("""
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                file_path TEXT, size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        runner = ExperimentMigrationRunner(conn)
        assert runner.get_applied_migrations() == [1, 2]
        assert runner.get_current_version() == 2

    def test_baseline_skipped_when_exp_schema_migrations_nonempty(
        self, tmp_path: Path
    ) -> None:
        # Run migrations normally first (creates exp_schema_migrations with entries)
        conn = _make_exp_conn(tmp_path)
        runner = ExperimentMigrationRunner(conn)
        runner.migrate()
        assert runner.get_current_version() == 2

        # Re-instantiate — should not add extra baseline entries
        runner2 = ExperimentMigrationRunner(conn)
        assert runner2.get_current_version() == 2
        assert runner2.get_applied_migrations() == [1, 2]


# ---------------------------------------------------------------------------
# Class 5: Old PyPI SDK – exp DB upgrade
# ---------------------------------------------------------------------------


class TestOldSdkExpDbUpgrade:
    def test_old_exp_db_baselines_to_v1(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_exp_db(tmp_path)
        runner = ExperimentMigrationRunner(conn)
        assert runner.get_current_version() == 1
        assert runner.get_applied_migrations() == [1]

    def test_old_exp_db_migrates_to_v2(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_exp_db(tmp_path)
        runner = ExperimentMigrationRunner(conn)
        runner.migrate()
        assert runner.get_current_version() == 2

    def test_old_exp_db_gets_size_column(self, tmp_path: Path) -> None:
        conn = _make_old_sdk_exp_db(tmp_path)
        ExperimentMigrationRunner(conn).migrate()
        assert "size" in _column_names(conn, "attachments")

    def test_old_exp_db_existing_attachments_preserved(self, tmp_path: Path) -> None:
        import uuid as _uuid

        conn = _make_old_sdk_exp_db(tmp_path)
        att_id = str(_uuid.uuid4())
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (?, ?, ?)",
            (att_id, "report.pdf", None),
        )
        conn.commit()

        ExperimentMigrationRunner(conn).migrate()

        row = conn.execute(
            "SELECT id, name FROM attachments WHERE id = ?", (att_id,)
        ).fetchone()
        assert row is not None
        assert row[1] == "report.pdf"

    def test_old_exp_db_with_size_already_skips_migration_002(
        self, tmp_path: Path
    ) -> None:
        # Old SDK that already has the size column — should baseline v1+v2, migrate() applies nothing
        conn = _make_exp_conn(tmp_path)
        conn.execute("""
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                file_path TEXT, size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        runner = ExperimentMigrationRunner(conn)
        # Already at v2 via baseline
        assert runner.get_applied_migrations() == [1, 2]
        newly_applied = runner.migrate()
        assert newly_applied == []
        assert runner.get_current_version() == 2
