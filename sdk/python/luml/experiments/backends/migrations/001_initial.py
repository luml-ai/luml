import sqlite3

VERSION = 1
DESCRIPTION = "Initial schema"


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            group_name TEXT,
            tags TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_groups (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS experiments")
    cursor.execute("DROP TABLE IF EXISTS experiment_groups")
    conn.commit()
