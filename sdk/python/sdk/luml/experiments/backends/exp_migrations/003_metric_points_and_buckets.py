# flake8: noqa: E501
import sqlite3

from luml.experiments.backends._exceptions import LegacyMetricRowsError
from luml.experiments.backends.metric_schema import (
    BUCKET_MAX_LEVEL,
    BUCKET_MIN_LEVEL,
    NUMERIC_SQL,
    SUMMABLE_SQL,
)

VERSION = 3
DESCRIPTION = "Compact metric points with aggregation buckets"

_CREATE_TABLES = (
    """
    CREATE TABLE metric_keys (
        id INTEGER PRIMARY KEY,
        key TEXT NOT NULL UNIQUE
    )
    """,
    # logged_at takes no storage. It makes the view's logged_at a table column with
    # declared type TIMESTAMP, which released SDKs (PARSE_DECLTYPES) read as datetime.
    """
    CREATE TABLE metric_points (
        metric_id INTEGER NOT NULL,
        step INTEGER NOT NULL,
        value REAL,
        logged_ms INTEGER,
        logged_at TIMESTAMP GENERATED ALWAYS AS
            (strftime('%Y-%m-%d %H:%M:%S', logged_ms / 1000, 'unixepoch')) VIRTUAL,
        PRIMARY KEY (metric_id, step)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE metric_buckets (
        level INTEGER NOT NULL,
        metric_id INTEGER NOT NULL,
        bucket INTEGER NOT NULL,
        count INTEGER NOT NULL,
        finite_count INTEGER NOT NULL,
        min REAL,
        max REAL,
        sum REAL,
        first_step INTEGER NOT NULL,
        last_step INTEGER NOT NULL,
        PRIMARY KEY (level, metric_id, bucket)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE exp_schema_info (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    ) WITHOUT ROWID
    """,
)

_CREATE_VIEW = """
    CREATE VIEW dynamic_metrics AS
    SELECT k.key AS key, p.value AS value, p.step AS step, p.logged_at AS logged_at
    FROM metric_points p JOIN metric_keys k ON k.id = p.metric_id
"""

_CREATE_TRIGGER = """
    CREATE TRIGGER dynamic_metrics_no_legacy_insert INSTEAD OF INSERT ON dynamic_metrics
    BEGIN
        SELECT RAISE(ABORT, 'this experiment uses schema revision 3; upgrade luml-sdk to write to it');
    END
"""

_SCHEMA_INFO = (
    ("min_reader_revision", "2"),
    ("min_writer_revision", "3"),
    ("bucket_min_level", str(BUCKET_MIN_LEVEL)),
    ("bucket_max_level", str(BUCKET_MAX_LEVEL)),
)

# Released SDKs bound numpy integers as their raw little-endian bytes.
_NUMPY_STEP = "typeof(step) = 'blob' AND length(step) IN (4, 8)"
_UNSUPPORTED_ROW = (
    f"typeof(key) <> 'text' OR NOT (typeof(step) = 'integer' OR ({_NUMPY_STEP}))"
)
_DECODE_STEP = "luml_decode_numpy_step"

_COUNT_UNSUPPORTED = f"""
    SELECT count(*), (SELECT 'key ' || quote(key) || ', step ' || quote(step)
                      FROM dynamic_metrics WHERE {_UNSUPPORTED_ROW} LIMIT 1)
    FROM dynamic_metrics WHERE {_UNSUPPORTED_ROW}
"""

# Ids follow key order, so the copy below walks the old (key, step) index in the
# order of the new (metric_id, step) key.
_COPY_KEYS = """
    INSERT INTO metric_keys (key)
    SELECT DISTINCT key FROM dynamic_metrics ORDER BY key
"""

# Fractional seconds are cut to milliseconds as text: SQLite's date functions round
# them, which would move 00:00:00.9996 to the next second.
_FRACTION = "substr(d.logged_at, 21)"
_FRACTION_DIGITS = f"substr({_FRACTION}, 1, length({_FRACTION}) - length(ltrim({_FRACTION}, '0123456789')))"
_LOGGED_MS = f"""
    CASE
        WHEN typeof(d.logged_at) <> 'text' THEN NULL
        WHEN substr(d.logged_at, 20, 1) <> '.' THEN
            CAST(strftime('%s', d.logged_at) AS INTEGER) * 1000
        ELSE
            CAST(strftime('%s', substr(d.logged_at, 1, 19) || ltrim({_FRACTION}, '0123456789')) AS INTEGER) * 1000
            + CAST(substr({_FRACTION_DIGITS} || '000', 1, 3) AS INTEGER)
    END
"""

_COPY_INTEGER_STEPS = f"""
    INSERT INTO metric_points (metric_id, step, value, logged_ms)
    SELECT k.id, d.step, d.value, {_LOGGED_MS}
    FROM dynamic_metrics d JOIN metric_keys k ON k.key = d.key
    WHERE typeof(d.step) = 'integer'
    ORDER BY k.id, d.step
"""

# A decoded step can equal a step stored as an integer: the later logged_at wins,
# and on a tie the row already stored, the integer one.
_COPY_NUMPY_STEPS = f"""
    INSERT INTO metric_points (metric_id, step, value, logged_ms)
    SELECT k.id, {_DECODE_STEP}(d.step), d.value, {_LOGGED_MS}
    FROM dynamic_metrics d JOIN metric_keys k ON k.key = d.key
    WHERE typeof(d.step) = 'blob' AND length(d.step) IN (4, 8)
    ORDER BY d.key, d.step
    ON CONFLICT (metric_id, step) DO UPDATE
    SET value = excluded.value, logged_ms = excluded.logged_ms
    WHERE excluded.logged_ms > metric_points.logged_ms
       OR (metric_points.logged_ms IS NULL AND excluded.logged_ms IS NOT NULL)
"""

_NUMERIC = NUMERIC_SQL.format("value")
_FINITE = SUMMABLE_SQL.format("value")

_BUILD_POINT_LEVEL = f"""
    INSERT INTO metric_buckets
        (level, metric_id, bucket, count, finite_count, min, max, sum, first_step, last_step)
    SELECT {BUCKET_MIN_LEVEL}, metric_id, step >> {2 * BUCKET_MIN_LEVEL}, count(*),
           count(CASE WHEN {_FINITE} THEN 1 END),
           min(CASE WHEN {_NUMERIC} THEN value END),
           max(CASE WHEN {_NUMERIC} THEN value END),
           sum(CASE WHEN {_FINITE} THEN value END),
           min(step), max(step)
    FROM metric_points
    GROUP BY metric_id, step >> {2 * BUCKET_MIN_LEVEL}
"""

_BUILD_UPPER_LEVEL = """
    INSERT INTO metric_buckets
        (level, metric_id, bucket, count, finite_count, min, max, sum, first_step, last_step)
    SELECT ?, metric_id, bucket >> 2, sum(count), sum(finite_count), min(min), max(max),
           sum(sum), min(first_step), max(last_step)
    FROM metric_buckets
    WHERE level = ?
    GROUP BY metric_id, bucket >> 2
"""


def _decode_numpy_step(raw: bytes) -> int:
    return int.from_bytes(raw, "little", signed=True)


def _legacy_table_exists(cursor: sqlite3.Cursor) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'dynamic_metrics'"
    )
    return cursor.fetchone() is not None


def _register_step_decoder(conn: sqlite3.Connection) -> None:
    """Registers the decoder unless the connection has it from an earlier attempt.

    SQLite refuses to redefine a function while any statement of the connection is
    active, and a migration retried on a pooled connection would otherwise do that.
    """
    try:
        if conn.execute(f"SELECT {_DECODE_STEP}(x'0100')").fetchall() == [(1,)]:
            return
    except sqlite3.OperationalError:
        pass
    conn.create_function(_DECODE_STEP, 1, _decode_numpy_step, deterministic=True)


def _copy_legacy_metrics(conn: sqlite3.Connection, cursor: sqlite3.Cursor) -> None:
    count, example = cursor.execute(_COUNT_UNSUPPORTED).fetchall()[0]
    if count:
        raise LegacyMetricRowsError(count, example)
    _register_step_decoder(conn)
    cursor.execute(_COPY_KEYS)
    cursor.execute(_COPY_INTEGER_STEPS)
    cursor.execute(_COPY_NUMPY_STEPS)
    cursor.execute("DROP TABLE dynamic_metrics")


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    for statement in _CREATE_TABLES:
        cursor.execute(statement)
    if _legacy_table_exists(cursor):
        _copy_legacy_metrics(conn, cursor)
    cursor.execute(_BUILD_POINT_LEVEL)
    for level in range(BUCKET_MIN_LEVEL + 1, BUCKET_MAX_LEVEL + 1):
        cursor.execute(_BUILD_UPPER_LEVEL, (level, level - 1))
    cursor.execute(_CREATE_VIEW)
    cursor.execute(_CREATE_TRIGGER)
    cursor.executemany(
        "INSERT INTO exp_schema_info (key, value) VALUES (?, ?)", _SCHEMA_INFO
    )
    cursor.execute("PRAGMA user_version = 3")
