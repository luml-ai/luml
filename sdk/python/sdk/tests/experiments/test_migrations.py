# flake8: noqa: E501
import importlib
import sqlite3
import uuid
from pathlib import Path

migration_001 = importlib.import_module(
    "luml.experiments.backends.exp_migrations.001_initial_schema"
)
migration_002 = importlib.import_module(
    "luml.experiments.backends.exp_migrations.002_add_attachment_size"
)
from luml.experiments.backends.sqlite import SQLiteBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_v1_db(path: Path) -> sqlite3.Connection:
    """Create a DB at version 1 (initial schema, no size column)."""
    conn = sqlite3.connect(str(path))
    migration_001.up(conn)
    conn.commit()
    return conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Migration 002 – uuid4 backfill for NULL ids
# ---------------------------------------------------------------------------


class TestMigration002UuidBackfill:
    def test_null_id_is_assigned_uuid(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        # Insert a row with NULL id (old SDK style)
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (NULL, 'file.txt', NULL)"
        )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT id FROM attachments WHERE name = 'file.txt'")
        row = cursor.fetchone()
        assert row is not None
        assigned_id = row[0]
        assert assigned_id is not None
        # Must be a valid UUID4 string
        parsed = uuid.UUID(assigned_id)
        assert parsed.version == 4

    def test_non_null_id_is_unchanged(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        existing_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (?, 'kept.txt', NULL)",
            (existing_id,),
        )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT id FROM attachments WHERE name = 'kept.txt'")
        row = cursor.fetchone()
        assert row[0] == existing_id

    def test_multiple_null_ids_each_get_unique_uuid(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        for i in range(3):
            conn.execute(
                "INSERT INTO attachments (id, name, file_path) VALUES (NULL, ?, NULL)",
                (f"file_{i}.txt",),
            )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT id FROM attachments")
        ids = [row[0] for row in cursor.fetchall()]
        assert all(i is not None for i in ids)
        assert len(set(ids)) == 3  # all unique

    def test_mixed_null_and_non_null_ids(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        existing_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (?, 'existing.txt', NULL)",
            (existing_id,),
        )
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (NULL, 'new.txt', NULL)"
        )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT id, name FROM attachments")
        rows = {row[1]: row[0] for row in cursor.fetchall()}
        assert rows["existing.txt"] == existing_id
        assert rows["new.txt"] is not None
        assert rows["new.txt"] != existing_id
        uuid.UUID(rows["new.txt"])  # must be a valid UUID


# ---------------------------------------------------------------------------
# Migration 002 – size backfill using rowid
# ---------------------------------------------------------------------------


class TestMigration002SizeBackfill:
    def test_size_backfilled_for_existing_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        # Create the attachments directory next to the db (as the backend does)
        attachments_dir = db_path.parent / "attachments"
        attachments_dir.mkdir()

        file_content = b"hello world"
        attachment_file = attachments_dir / "sample.bin"
        attachment_file.write_bytes(file_content)

        # Insert a row with NULL id and a valid relative file_path
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (NULL, 'sample', 'sample.bin')"
        )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT size FROM attachments WHERE name = 'sample'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == len(file_content)

    def test_size_remains_null_when_file_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        attachments_dir = db_path.parent / "attachments"
        attachments_dir.mkdir()

        # file_path points to a non-existent file
        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (NULL, 'ghost', 'does_not_exist.bin')"
        )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT size FROM attachments WHERE name = 'ghost'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is None

    def test_size_null_when_file_path_is_null(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        conn.execute(
            "INSERT INTO attachments (id, name, file_path) VALUES (NULL, 'no_path', NULL)"
        )
        conn.commit()

        migration_002.up(conn)
        conn.commit()

        cursor = conn.execute("SELECT size FROM attachments WHERE name = 'no_path'")
        row = cursor.fetchone()
        assert row[0] is None


# ---------------------------------------------------------------------------
# Migration 002 – down() removes size column
# ---------------------------------------------------------------------------


class TestMigration002Down:
    def test_down_removes_size_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        migration_002.up(conn)
        conn.commit()

        assert "size" in _column_names(conn, "attachments")

        migration_002.down(conn)
        conn.commit()

        assert "size" not in _column_names(conn, "attachments")

    def test_down_sets_user_version_to_1(self, tmp_path: Path) -> None:
        db_path = tmp_path / "exp.db"
        conn = _make_v1_db(db_path)

        migration_002.up(conn)
        conn.commit()

        migration_002.down(conn)
        conn.commit()

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1


# ---------------------------------------------------------------------------
# get_experiment_data triggers migration on old (v1-only) database
# ---------------------------------------------------------------------------


def _register_experiment_in_meta(backend: SQLiteBackend, exp_id: str) -> None:
    """Insert a minimal experiment row into the meta DB without touching exp.db."""
    meta_conn = backend._get_meta_connection()
    # Ensure a default group exists
    meta_conn.execute(
        "INSERT OR IGNORE INTO experiment_groups (id, name) VALUES (?, ?)",
        ("default-group-id", "default"),
    )
    group_row = meta_conn.execute(
        "SELECT id FROM experiment_groups WHERE name = 'default'"
    ).fetchone()
    group_id = group_row[0]
    meta_conn.execute(
        "INSERT OR REPLACE INTO experiments (id, name, group_id) VALUES (?, ?, ?)",
        (exp_id, exp_id, group_id),
    )
    meta_conn.commit()


class TestGetExperimentDataTriggersMigration:
    def _make_old_sdk_experiment_db(self, base: Path, exp_id: str) -> None:
        """
        Simulate an old SDK: create the exp directory and an exp.db that only
        has migration_001 applied (no exp_schema_migrations table, no size column).
        """
        exp_dir = base / exp_id
        exp_dir.mkdir(parents=True)
        (exp_dir / "attachments").mkdir()

        db_path = exp_dir / "exp.db"
        conn = sqlite3.connect(str(db_path))
        migration_001.up(conn)
        conn.commit()
        conn.close()

    def test_get_experiment_data_applies_migration_002(self, tmp_path: Path) -> None:
        base = tmp_path / "experiments"
        base.mkdir()
        exp_id = "old-exp-001"

        # SQLiteBackend.__init__ sets up the meta DB
        backend = SQLiteBackend(str(base))
        # Create the experiment DB at v1 only (simulates old SDK)
        self._make_old_sdk_experiment_db(base, exp_id)
        # Register in meta without touching the exp DB
        _register_experiment_in_meta(backend, exp_id)

        # get_experiment_data must succeed and migrate the DB
        data = backend.get_experiment_data(exp_id)
        assert data is not None

        # Verify the size column now exists (migration_002 was applied)
        exp_conn = sqlite3.connect(str(base / exp_id / "exp.db"))
        cols = _column_names(exp_conn, "attachments")
        exp_conn.close()
        assert "size" in cols

    def test_get_experiment_data_migrated_db_has_user_version_2(
        self, tmp_path: Path
    ) -> None:
        base = tmp_path / "experiments"
        base.mkdir()
        exp_id = "old-exp-002"

        backend = SQLiteBackend(str(base))
        self._make_old_sdk_experiment_db(base, exp_id)
        _register_experiment_in_meta(backend, exp_id)

        backend.get_experiment_data(exp_id)

        exp_conn = sqlite3.connect(str(base / exp_id / "exp.db"))
        version = exp_conn.execute("PRAGMA user_version").fetchone()[0]
        exp_conn.close()
        assert version == 2
