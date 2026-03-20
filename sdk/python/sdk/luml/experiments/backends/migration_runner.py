import importlib
import sqlite3
from typing import Any

from luml.experiments.backends.migrations import MIGRATIONS_DIR


class MigrationRunner:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._ensure_migrations_table()
        self._apply_baseline_if_needed()

    def _ensure_migrations_table(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _apply_baseline_if_needed(self) -> None:
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM schema_migrations")
        if cursor.fetchone()[0] > 0:
            return

        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='experiment_groups'"
        )
        if cursor.fetchone() is None:
            return

        cursor.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (1,),
        )
        self.conn.commit()

    def get_current_version(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(version) FROM schema_migrations")
        result = cursor.fetchone()[0]
        return result if result is not None else 0

    def get_applied_migrations(self) -> list[int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        return [row[0] for row in cursor.fetchall()]

    def _discover_migrations(self) -> list[dict[str, Any]]:
        migrations = []

        for file_path in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
            if file_path.name == "__init__.py":
                continue

            module_name = f"luml.experiments.backends.migrations.{file_path.stem}"
            try:
                module = importlib.import_module(module_name)
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
            except ImportError as e:
                raise ImportError(
                    f"Failed to load migration {file_path.name}: {e}"
                ) from e

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
                    "INSERT INTO schema_migrations (version) VALUES (?)",
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
                    "DELETE FROM schema_migrations WHERE version = ?",
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
