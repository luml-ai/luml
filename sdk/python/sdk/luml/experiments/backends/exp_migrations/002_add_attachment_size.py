import sqlite3
from pathlib import Path

VERSION = 2
DESCRIPTION = "Add size column to attachments table"


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE attachments ADD COLUMN size INTEGER")

    cursor.execute("PRAGMA database_list")
    db_path = Path(cursor.fetchone()[2])
    attachments_dir = db_path.parent / "attachments"

    cursor.execute("SELECT id, file_path FROM attachments WHERE file_path IS NOT NULL")
    for att_id, file_path in cursor.fetchall():
        full_path = attachments_dir / file_path
        if full_path.exists():
            cursor.execute(
                "UPDATE attachments SET size = ? WHERE id = ?",
                (full_path.stat().st_size, att_id),
            )

    cursor.execute("PRAGMA user_version = 2")


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE attachments DROP COLUMN size")
    cursor.execute("PRAGMA user_version = 1")
