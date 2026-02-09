"""
CLI for managing meta.db migrations.

Usage:
    python -m luml.experiments.backends.migrations status [--db PATH]
    python -m luml.experiments.backends.migrations migrate [--db PATH] [--target VERSION]
    python -m luml.experiments.backends.migrations rollback [--db PATH] [--target VERSION]
    python -m luml.experiments.backends.migrations list
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from luml.experiments.backends.migration_runner import MigrationRunner
from luml.experiments.backends.migrations import MIGRATIONS_DIR


def get_default_db_path() -> Path:
    import os

    base = os.environ.get("LUML_EXPERIMENTS_PATH", Path.home() / "experiments")
    return Path(base) / "meta.db"


def cmd_status(args: argparse.Namespace) -> None:
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run your experiment code first to create the database.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    runner = MigrationRunner(conn)
    status = runner.get_status()

    print(f"Database: {db_path}")
    print(f"Current version: {status['current_version']}")
    print(f"Applied migrations: {status['applied_count']}")
    print(f"Pending migrations: {status['pending_count']}")

    if status["applied_versions"]:
        print("\nApplied:")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version"
        )
        for version, applied_at in cursor.fetchall():
            print(f"  [{version}] (applied: {applied_at})")

    if status["pending_versions"]:
        print("\nPending:")
        for m in runner.get_pending_migrations():
            print(f"  [{m['version']}] {m['description']} ({m['file']})")

    conn.close()


def cmd_migrate(args: argparse.Namespace) -> None:
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    runner = MigrationRunner(conn)

    pending = runner.get_pending_migrations()
    if not pending:
        print("No pending migrations.")
        conn.close()
        return

    target = args.target
    if target:
        pending = [m for m in pending if m["version"] <= target]

    print(f"Applying {len(pending)} migration(s)...")
    for m in pending:
        print(f"  [{m['version']}] {m['description']}")

    try:
        applied = runner.migrate(target_version=target)
        print(f"\nSuccessfully applied {len(applied)} migration(s).")
    except RuntimeError as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


def cmd_rollback(args: argparse.Namespace) -> None:
    db_path = Path(args.db)

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    runner = MigrationRunner(conn)

    current = runner.get_current_version()
    target = args.target

    if current <= target:
        print(f"Current version ({current}) is already at or below target ({target}).")
        conn.close()
        return

    to_rollback = [v for v in runner.get_applied_migrations() if v > target]
    print(f"Rolling back {len(to_rollback)} migration(s) to version {target}...")

    try:
        rolled_back = runner.rollback(target_version=target)
        print(f"\nSuccessfully rolled back {len(rolled_back)} migration(s).")
    except RuntimeError as e:
        print(f"\nRollback failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


def cmd_list(args: argparse.Namespace) -> None:
    print(f"Migrations directory: {MIGRATIONS_DIR}\n")

    import importlib

    migrations = []
    for file_path in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
        module_name = f"luml.experiments.backends.migrations.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "VERSION"):
                migrations.append(
                    {
                        "version": module.VERSION,
                        "description": getattr(module, "DESCRIPTION", ""),
                        "has_down": hasattr(module, "down"),
                        "file": file_path.name,
                    }
                )
        except ImportError as e:
            print(f"  [!] Error loading {file_path.name}: {e}")

    if not migrations:
        print("No migrations found.")
        return

    print("Available migrations:")
    for m in sorted(migrations, key=lambda x: x["version"]):
        rollback_indicator = "↩" if m["has_down"] else " "
        print(f"  [{m['version']:03d}] {rollback_indicator} {m['description']}")
        print(f"         {m['file']}")

    print("\n↩ = supports rollback")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage luml meta.db migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show migration status")
    status_parser.add_argument(
        "--db", default=str(get_default_db_path()), help="Path to meta.db"
    )
    status_parser.set_defaults(func=cmd_status)

    migrate_parser = subparsers.add_parser("migrate", help="Apply pending migrations")
    migrate_parser.add_argument(
        "--db", default=str(get_default_db_path()), help="Path to meta.db"
    )
    migrate_parser.add_argument(
        "--target", type=int, help="Target version (apply up to this version)"
    )
    migrate_parser.set_defaults(func=cmd_migrate)

    rollback_parser = subparsers.add_parser("rollback", help="Rollback migrations")
    rollback_parser.add_argument(
        "--db", default=str(get_default_db_path()), help="Path to meta.db"
    )
    rollback_parser.add_argument(
        "--target",
        type=int,
        default=0,
        help="Target version (rollback to this version)",
    )
    rollback_parser.set_defaults(func=cmd_rollback)

    list_parser = subparsers.add_parser("list", help="List all available migrations")
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
