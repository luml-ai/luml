import sqlite3

VERSION = 3
DESCRIPTION = "Add size column to models table"


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE models ADD COLUMN size INTEGER")
    conn.commit()


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE models DROP COLUMN size")
    conn.commit()
