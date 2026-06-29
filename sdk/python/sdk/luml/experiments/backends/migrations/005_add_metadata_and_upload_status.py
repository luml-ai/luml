import sqlite3

VERSION = 5
DESCRIPTION = "Add metadata JSON and upload_status columns to experiments table"


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE experiments ADD COLUMN metadata TEXT")
    cursor.execute("ALTER TABLE experiments ADD COLUMN upload_status TEXT")
    # Backfill pre-existing rows to 'unknown'. New rows default to
    # 'not_uploaded' at the application layer (see ExperimentTracker).
    cursor.execute(
        "UPDATE experiments SET upload_status = 'unknown' WHERE upload_status IS NULL"
    )


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE experiments DROP COLUMN metadata")
    cursor.execute("ALTER TABLE experiments DROP COLUMN upload_status")
