import sqlite3
import uuid

VERSION = 2
DESCRIPTION = "Fixed experiment and group relationship"

DEFAULT_GROUP_NAME = "default"


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    cursor.execute("SELECT rowid, name FROM experiment_groups WHERE id IS NULL")
    for row in cursor.fetchall():
        cursor.execute(
            "UPDATE experiment_groups SET id = ? WHERE rowid = ?",
            (str(uuid.uuid4()), row[0]),
        )

    cursor.execute("""
        SELECT name FROM experiment_groups
        GROUP BY name HAVING COUNT(*) > 1
    """)
    duplicate_names = [r[0] for r in cursor.fetchall()]
    for dup_name in duplicate_names:
        cursor.execute(
            "SELECT rowid, created_at FROM experiment_groups "
            "WHERE name = ? ORDER BY created_at",
            (dup_name,),
        )
        rows = cursor.fetchall()
        for rowid, created_at in rows[1:]:
            new_name = f"{dup_name} ({created_at})"
            cursor.execute(
                "UPDATE experiment_groups SET name = ? WHERE rowid = ?",
                (new_name, rowid),
            )

    cursor.execute(
        "SELECT COUNT(*) FROM experiments WHERE group_name IS NULL OR group_name = ''"
    )
    orphan_count = cursor.fetchone()[0]
    if orphan_count > 0:
        cursor.execute(
            "SELECT id FROM experiment_groups WHERE name = ?",
            (DEFAULT_GROUP_NAME,),
        )
        existing = cursor.fetchone()
        if existing is None:
            default_group_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO experiment_groups (id, name) VALUES (?, ?)",
                (default_group_id, DEFAULT_GROUP_NAME),
            )
        cursor.execute(
            "UPDATE experiments SET group_name = ? "
            "WHERE group_name IS NULL OR group_name = ''",
            (DEFAULT_GROUP_NAME,),
        )

    cursor.execute(
        "ALTER TABLE experiments ADD COLUMN group_id TEXT "
        "REFERENCES experiment_groups(id)"
    )
    cursor.execute("""
        UPDATE experiments
        SET group_id = (
            SELECT eg.id FROM experiment_groups eg
            WHERE eg.name = experiments.group_name
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tags TEXT,
            path TEXT,
            experiment_id TEXT REFERENCES experiments(id)
        )
    """)

    cursor.execute("ALTER TABLE experiments DROP COLUMN group_name")
    cursor.execute("ALTER TABLE experiments ADD COLUMN static_params TEXT")
    cursor.execute("ALTER TABLE experiments ADD COLUMN dynamic_params TEXT")

    cursor.execute("ALTER TABLE experiment_groups ADD COLUMN tags TEXT")

    cursor.execute(
        "CREATE UNIQUE INDEX "
        "IF NOT EXISTS idx_experiment_groups_name ON experiment_groups(name)"
    )


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    cursor.execute("DROP INDEX IF EXISTS idx_experiment_groups_name")

    cursor.execute("ALTER TABLE experiment_groups DROP COLUMN tags")

    cursor.execute("ALTER TABLE experiments ADD COLUMN group_name TEXT")
    cursor.execute("""
        UPDATE experiments
        SET group_name = (
            SELECT eg.name FROM experiment_groups eg
            WHERE eg.id = experiments.group_id
        )
    """)
    cursor.execute("ALTER TABLE experiments DROP COLUMN group_id")
    cursor.execute("ALTER TABLE experiments DROP COLUMN static_params")
    cursor.execute("ALTER TABLE experiments DROP COLUMN dynamic_params")
    cursor.execute("DROP TABLE IF EXISTS models")
