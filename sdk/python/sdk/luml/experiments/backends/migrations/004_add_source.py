import sqlite3

VERSION = 4
DESCRIPTION = "Add source column to experiments and models tables"


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE experiments ADD COLUMN source TEXT")
    cursor.execute("ALTER TABLE models ADD COLUMN source TEXT")
    cursor.execute("ALTER TABLE models ADD COLUMN description TEXT")


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE experiments DROP COLUMN source")
    cursor.execute("ALTER TABLE models DROP COLUMN source")
    cursor.execute("ALTER TABLE models DROP COLUMN description")
