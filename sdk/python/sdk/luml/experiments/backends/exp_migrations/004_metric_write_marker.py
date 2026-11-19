# flake8: noqa: E501
import sqlite3

VERSION = 4
DESCRIPTION = "Per-metric write marker"

# Raised by every flush that writes a point of the metric, so readers that cache
# buckets can tell an overwrite of a step apart from no change at all.
_ADD_WRITES = "ALTER TABLE metric_keys ADD COLUMN writes INTEGER NOT NULL DEFAULT 0"

_REPLACE_TRIGGER = (
    "DROP TRIGGER dynamic_metrics_no_legacy_insert",
    """
    CREATE TRIGGER dynamic_metrics_no_legacy_insert INSTEAD OF INSERT ON dynamic_metrics
    BEGIN
        SELECT RAISE(ABORT, 'this experiment uses schema revision 4; upgrade luml-sdk to write to it');
    END
    """,
)


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(_ADD_WRITES)
    for statement in _REPLACE_TRIGGER:
        cursor.execute(statement)
    # A writer that knows only revision 3 would leave the marker unchanged.
    cursor.execute(
        "UPDATE exp_schema_info SET value = '4' WHERE key = 'min_writer_revision'"
    )
    cursor.execute("PRAGMA user_version = 4")
