import sqlite3

VERSION = 6
DESCRIPTION = "Add remote artifact mappings"


def up(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS remote_artifacts (
            local_type TEXT NOT NULL,
            local_id TEXT NOT NULL,
            orbit_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (local_type, local_id, orbit_id)
        )
    """)


def down(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS remote_artifacts")
