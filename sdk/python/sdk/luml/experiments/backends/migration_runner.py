import contextlib
import importlib.util
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from luml.experiments.backends._exceptions import LumlExperimentsError
from luml.experiments.backends.migrations import MIGRATIONS_DIR

MIGRATION_BUSY_MS = 120_000


class BaseMigrationRunner:
    def __init__(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        migrations_dir: Path,
    ) -> None:
        self.conn = conn
        self.table_name = table_name
        self.migrations_dir = migrations_dir
        self._ensure_migrations_table()
        self._apply_baseline_if_needed()

    def _ensure_migrations_table(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _apply_baseline_if_needed(self) -> None:
        """Override in subclasses to mark pre-existing schema as already migrated."""

    def get_current_version(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT MAX(version) FROM {self.table_name}")
        result = cursor.fetchone()[0]
        return result if result is not None else 0

    def get_applied_migrations(self) -> list[int]:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT version FROM {self.table_name} ORDER BY version")
        return [row[0] for row in cursor.fetchall()]

    def _discover_migrations(self) -> list[dict[str, Any]]:
        migrations = []

        for file_path in sorted(self.migrations_dir.glob("[0-9]*.py")):
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception as e:
                raise ImportError(
                    f"Failed to load migration {file_path.name}: {e}"
                ) from e
            if hasattr(module, "VERSION") and hasattr(module, "up"):
                migrations.append(
                    {
                        "version": module.VERSION,
                        "description": getattr(module, "DESCRIPTION", ""),
                        "up": module.up,
                        "down": getattr(module, "down", None),
                        "file": file_path.name,
                    }
                )

        return sorted(migrations, key=lambda m: m["version"])

    def get_pending_migrations(self) -> list[dict[str, Any]]:
        applied = set(self.get_applied_migrations())
        all_migrations = self._discover_migrations()
        return [m for m in all_migrations if m["version"] not in applied]

    def _next_pending(
        self, migrations: list[dict[str, Any]], target_version: int | None
    ) -> dict[str, Any] | None:
        # A database already past every migration this code knows was written by a
        # newer SDK; filling gaps below its revision could undo what that SDK did.
        if migrations and self.get_current_version() > migrations[-1]["version"]:
            return None
        applied = set(self.get_applied_migrations())
        for migration in migrations:
            if target_version is not None and migration["version"] > target_version:
                return None
            if migration["version"] not in applied:
                return migration
        return None

    @staticmethod
    def _begin_immediate(cursor: sqlite3.Cursor) -> None:
        # Another process may hold the lock through a migration that takes longer
        # than the connection's usual busy timeout.
        timeout_ms = cursor.execute("PRAGMA busy_timeout").fetchone()[0]
        cursor.execute(f"PRAGMA busy_timeout = {max(timeout_ms, MIGRATION_BUSY_MS)}")
        try:
            cursor.execute("BEGIN IMMEDIATE")
        finally:
            cursor.execute(f"PRAGMA busy_timeout = {timeout_ms}")

    def migrate(self, target_version: int | None = None) -> list[int]:
        migrations = self._discover_migrations()
        applied_versions: list[int] = []
        if self._next_pending(migrations, target_version) is None:
            return applied_versions

        cursor = self.conn.cursor()
        while True:
            # Pending work is decided under the write lock, so a second process
            # migrating the same database waits and then finds nothing left to do.
            self._begin_immediate(cursor)
            migration = None
            try:
                migration = self._next_pending(migrations, target_version)
                if migration is not None:
                    migration["up"](self.conn)
                    cursor.execute(
                        f"INSERT INTO {self.table_name} (version) VALUES (?)",
                        (migration["version"],),
                    )
                self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                # A typed refusal already says what the caller can do about it.
                if migration is None or isinstance(e, LumlExperimentsError):
                    raise
                raise RuntimeError(
                    f"Migration {migration['version']} "
                    f"({migration['file']}) failed: {e}"
                ) from e
            if migration is None:
                return applied_versions
            applied_versions.append(migration["version"])

    def rollback(self, target_version: int = 0) -> list[int]:
        applied = self.get_applied_migrations()
        to_rollback = [v for v in reversed(applied) if v > target_version]

        all_migrations = {m["version"]: m for m in self._discover_migrations()}
        rolled_back = []
        cursor = self.conn.cursor()

        for version in to_rollback:
            migration = all_migrations.get(version)
            if not migration:
                raise RuntimeError(f"Migration {version} not found for rollback")

            if migration["down"] is None:
                raise RuntimeError(f"Migration {version} does not support rollback")

            try:
                cursor.execute("BEGIN")
                migration["down"](self.conn)
                cursor.execute(
                    f"DELETE FROM {self.table_name} WHERE version = ?",
                    (version,),
                )
                self.conn.commit()
                rolled_back.append(version)
            except Exception as e:
                self.conn.rollback()
                raise RuntimeError(
                    f"Rollback of migration {version} failed: {e}"
                ) from e

        return rolled_back

    def get_status(self) -> dict[str, Any]:
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()

        return {
            "current_version": self.get_current_version(),
            "applied_count": len(applied),
            "pending_count": len(pending),
            "applied_versions": applied,
            "pending_versions": [m["version"] for m in pending],
        }


class MetaDBMigrationRunner(BaseMigrationRunner):
    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__(conn, "schema_migrations", MIGRATIONS_DIR)

    def _apply_baseline_if_needed(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        if cursor.fetchone()[0] > 0:
            return

        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='experiment_groups'"
        )
        if cursor.fetchone() is None:
            return

        cursor.execute(
            f"INSERT INTO {self.table_name} (version) VALUES (?)",
            (1,),
        )
        self.conn.commit()


class ExperimentMigrationRunner(BaseMigrationRunner):
    def __init__(self, conn: sqlite3.Connection) -> None:
        from luml.experiments.backends.exp_migrations import EXP_MIGRATIONS_DIR

        super().__init__(conn, "exp_schema_migrations", EXP_MIGRATIONS_DIR)

    def _apply_baseline_if_needed(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
        if cursor.fetchone()[0] > 0:
            return

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='attachments'"
        )
        if cursor.fetchone() is None:
            return

        # OR IGNORE: another process may record the same baseline at the same time.
        cursor.execute(
            f"INSERT OR IGNORE INTO {self.table_name} (version) VALUES (?)", (1,)
        )

        cursor.execute("PRAGMA table_info(attachments)")
        cols = {row[1] for row in cursor.fetchall()}
        if "size" in cols:
            cursor.execute(
                f"INSERT OR IGNORE INTO {self.table_name} (version) VALUES (?)", (2,)
            )

        self.conn.commit()


MigrationRunner = MetaDBMigrationRunner

KNOWN_EXPERIMENT_REVISION = 3
# Released SDKs bring older databases to this revision whenever they open them.
READ_MIGRATION_REVISION = 2


@dataclass(frozen=True)
class ExperimentSchema:
    revision: int
    min_reader_revision: int = 0
    min_writer_revision: int = 0
    bucket_min_level: int | None = None
    bucket_max_level: int | None = None

    @property
    def has_metric_points(self) -> bool:
        return self.revision >= 3


def read_experiment_schema(
    conn: sqlite3.Connection, database: str = "main"
) -> ExperimentSchema:
    """The revision is the newest recorded migration, else `PRAGMA user_version`.

    `database` names an attached database to read instead of the main one.
    """
    tables = {
        row[0]
        for row in conn.execute(
            f"SELECT name FROM {database}.sqlite_master WHERE type = 'table' "
            "AND name IN ('exp_schema_migrations', 'exp_schema_info')"
        )
    }
    revision = None
    if "exp_schema_migrations" in tables:
        revision = conn.execute(
            f"SELECT MAX(version) FROM {database}.exp_schema_migrations"
        ).fetchone()[0]
    if revision is None:
        revision = conn.execute(f"PRAGMA {database}.user_version").fetchone()[0]
    info: dict[str, int] = {}
    if "exp_schema_info" in tables:
        for key, value in conn.execute(
            f"SELECT key, value FROM {database}.exp_schema_info"
        ):
            with contextlib.suppress(TypeError, ValueError):
                info[key] = int(value)
    return ExperimentSchema(
        revision=revision,
        min_reader_revision=info.get("min_reader_revision", 0),
        min_writer_revision=info.get("min_writer_revision", 0),
        bucket_min_level=info.get("bucket_min_level"),
        bucket_max_level=info.get("bucket_max_level"),
    )
