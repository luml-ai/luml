import importlib.util
import sqlite3
from pathlib import Path
from typing import Any

from luml.experiments.backends.migrations import MIGRATIONS_DIR


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

    def migrate(self, target_version: int | None = None) -> list[int]:
        pending = self.get_pending_migrations()
        if target_version is not None:
            pending = [m for m in pending if m["version"] <= target_version]

        applied_versions = []
        cursor = self.conn.cursor()

        for migration in pending:
            try:
                cursor.execute("BEGIN")
                migration["up"](self.conn)
                cursor.execute(
                    f"INSERT INTO {self.table_name} (version) VALUES (?)",
                    (migration["version"],),
                )
                self.conn.commit()
                applied_versions.append(migration["version"])
            except Exception as e:
                self.conn.rollback()
                raise RuntimeError(
                    f"Migration {migration['version']} "
                    f"({migration['file']}) failed: {e}"
                ) from e

        return applied_versions

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

        cursor.execute(f"INSERT INTO {self.table_name} (version) VALUES (?)", (1,))

        cursor.execute("PRAGMA table_info(attachments)")
        cols = {row[1] for row in cursor.fetchall()}
        if "size" in cols:
            cursor.execute(f"INSERT INTO {self.table_name} (version) VALUES (?)", (2,))

        self.conn.commit()


MigrationRunner = MetaDBMigrationRunner
