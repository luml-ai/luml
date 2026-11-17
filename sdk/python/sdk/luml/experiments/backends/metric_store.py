# flake8: noqa: E501
"""Metric storage of experiment schema revision 3: points, keys and buckets."""

import sqlite3
from itertools import groupby
from typing import Any

from luml.experiments.backends._exceptions import (
    InvalidBucketLevelError,
    TooManyBucketsError,
)
from luml.experiments.backends._write_buffer import BatchKeys, PendingRow
from luml.experiments.backends.data_types import (
    MetricBucket,
    MetricBuckets,
    MetricCatalog,
    MetricSummary,
)
from luml.experiments.backends.metric_schema import (
    BUCKET_MAX_LEVEL,
    BUCKET_MIN_LEVEL,
    NUMERIC_SQL,
    SUMMABLE_SQL,
)
from luml.experiments.backends.migration_runner import ExperimentSchema

MAX_RETURNED_BUCKETS = 20_000
MAX_BUCKET_LEVEL = 31

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_KEY_LOOKUP_CHUNK = 500

# Queued with the metric key in place of the id, which the write hook resolves.
METRIC_POINT_SQL = (
    "INSERT OR REPLACE INTO metric_points (metric_id, step, value, logged_ms) "
    "VALUES (?, ?, ?, ?)"
)

_POINT_INSERT = (
    "INSERT OR REPLACE INTO metric_points (metric_id, step, value, logged_ms) VALUES "
)
_MAX_ROWS_PER_INSERT = 4_096

# Revisions 0-2 stored whatever released SDKs were given; only these rows are read.
_LEGACY_ROW = "typeof(step) = 'integer' AND typeof(key) = 'text'"


def _value_aggregates(value: str) -> str:
    """count, finite_count, min, max and sum over the raw points of a group."""
    return (
        f"count(*), count(CASE WHEN {SUMMABLE_SQL.format(value)} THEN 1 END), "
        f"min(CASE WHEN {NUMERIC_SQL.format(value)} THEN {value} END), "
        f"max(CASE WHEN {NUMERIC_SQL.format(value)} THEN {value} END), "
        f"sum(CASE WHEN {SUMMABLE_SQL.format(value)} THEN {value} END)"
    )


_BUCKET_AGGREGATES = (
    "sum(c.count), sum(c.finite_count), min(c.min), max(c.max), sum(c.sum), "
    "min(c.first_step), max(c.last_step)"
)

_BUCKET_COLUMNS = "level, metric_id, bucket, count, finite_count, min, max, sum, first_step, last_step"

# One bucket per parameter row. HAVING drops a bucket without points, which can only be
# a bucket that never had any: points are replaced, never deleted, so REPLACE is exact.
_REBUILD_POINT_BUCKET = f"""
    INSERT OR REPLACE INTO metric_buckets ({_BUCKET_COLUMNS})
    SELECT {BUCKET_MIN_LEVEL}, ?1, ?2, {_value_aggregates("value")}, min(step), max(step)
    FROM metric_points
    WHERE metric_id = ?1
      AND step BETWEEN ?2 << {2 * BUCKET_MIN_LEVEL}
                   AND (?2 << {2 * BUCKET_MIN_LEVEL}) + {4**BUCKET_MIN_LEVEL - 1}
    HAVING count(*) > 0
"""

_REBUILD_UPPER_BUCKET = f"""
    INSERT OR REPLACE INTO metric_buckets ({_BUCKET_COLUMNS})
    SELECT ?3, ?1, ?2, {_BUCKET_AGGREGATES}
    FROM metric_buckets c
    WHERE c.level = ?3 - 1 AND c.metric_id = ?1 AND c.bucket BETWEEN ?2 * 4 AND ?2 * 4 + 3
    HAVING count(*) > 0
"""

# Fewer touched level-3 buckets than this are rebuilt a statement per bucket, which
# costs less than the set-based statements' fixed cost: write-through commits one point
# at a time.
_SET_REFRESH_MIN_BUCKETS = 32

# Lives on the writing connection; a rollback undoes its rows or its creation, and each
# refresh empties it first, so it never carries buckets from another flush.
_TOUCHED = "temp.luml_touched_buckets"
_CREATE_TOUCHED = f"""
    CREATE TABLE IF NOT EXISTS {_TOUCHED} (
        level INTEGER NOT NULL, metric_id INTEGER NOT NULL, bucket INTEGER NOT NULL,
        PRIMARY KEY (level, metric_id, bucket)
    ) WITHOUT ROWID
"""

# One statement per level for all touched buckets: a statement per bucket made a flush
# cost grow with the number of metrics it touched. The inner join drops a bucket
# without points, which can only be one that never had any: points are replaced, never
# deleted, so REPLACE is exact.
_REBUILD_POINT_LEVEL = f"""
    INSERT OR REPLACE INTO metric_buckets ({_BUCKET_COLUMNS})
    SELECT t.level, t.metric_id, t.bucket, {_value_aggregates("p.value")},
           min(p.step), max(p.step)
    FROM {_TOUCHED} t CROSS JOIN metric_points p
    WHERE t.level = {BUCKET_MIN_LEVEL} AND p.metric_id = t.metric_id
      AND p.step BETWEEN t.bucket << {2 * BUCKET_MIN_LEVEL}
                     AND (t.bucket << {2 * BUCKET_MIN_LEVEL}) + {4**BUCKET_MIN_LEVEL - 1}
    GROUP BY t.metric_id, t.bucket
"""

_TOUCH_PARENTS = f"""
    INSERT OR IGNORE INTO {_TOUCHED} (level, metric_id, bucket)
    SELECT ?1, metric_id, bucket >> 2 FROM {_TOUCHED} WHERE level = ?1 - 1
"""

_REBUILD_UPPER_LEVEL = f"""
    INSERT OR REPLACE INTO metric_buckets ({_BUCKET_COLUMNS})
    SELECT t.level, t.metric_id, t.bucket, {_BUCKET_AGGREGATES}
    FROM {_TOUCHED} t CROSS JOIN metric_buckets c
    WHERE t.level = ?1 AND c.level = ?1 - 1 AND c.metric_id = t.metric_id
      AND c.bucket BETWEEN t.bucket * 4 AND t.bucket * 4 + 3
    GROUP BY t.metric_id, t.bucket
"""


def choose_bucket_level(first_step: int, last_step: int, max_buckets: int) -> int:
    """The smallest level whose buckets cover `[first_step, last_step]` in at most
    `max_buckets` bucket widths, a level's width being `4 ** level` steps."""
    if max_buckets < 1:
        raise ValueError("max_buckets must be at least 1")
    if last_step < first_step:
        raise ValueError("last_step must not be smaller than first_step")
    span = last_step - first_step + 1
    level = 0
    while -(-span // 4**level) > max_buckets:
        level += 1
    return level


def _insert_rows(
    conn: sqlite3.Connection, insert: str, row_values: str, rows: list[tuple[Any, ...]]
) -> None:
    """Runs `insert` with `row_values` once per row, in order, many rows per statement.

    Each statement releases and retakes the GIL, and retaking it waits out a busy
    logging thread's time slice: one statement per row kept the timer flush from
    running alongside logging. Statements hold a power of two of rows, so the statement
    cache keeps a few sizes of them, the largest a few megabytes.
    """
    if not rows:
        return
    variables = conn.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)
    most = min(variables // len(rows[0]), _MAX_ROWS_PER_INSERT)
    size = _MAX_ROWS_PER_INSERT
    start = 0
    while start < len(rows):
        while size > 1 and size > min(most, len(rows) - start):
            size //= 2
        conn.execute(
            insert + ", ".join([row_values] * size),
            [value for row in rows[start : start + size] for value in row],
        )
        start += size


def refresh_buckets(conn: sqlite3.Connection, touched: set[tuple[int, int]]) -> None:
    """Recomputes the given `(metric_id, level-3 bucket)` pairs and their parents at
    every stored level from the committed points, inside the caller's transaction."""
    if len(touched) < _SET_REFRESH_MIN_BUCKETS:
        _refresh_each_bucket(conn, touched)
    else:
        _refresh_bucket_set(conn, touched)


def _refresh_each_bucket(
    conn: sqlite3.Connection, touched: set[tuple[int, int]]
) -> None:
    conn.executemany(_REBUILD_POINT_BUCKET, sorted(touched))
    level_buckets = touched
    for level in range(BUCKET_MIN_LEVEL + 1, BUCKET_MAX_LEVEL + 1):
        level_buckets = {
            (metric_id, bucket >> 2) for metric_id, bucket in level_buckets
        }
        conn.executemany(
            _REBUILD_UPPER_BUCKET,
            [(metric_id, bucket, level) for metric_id, bucket in sorted(level_buckets)],
        )


def _refresh_bucket_set(
    conn: sqlite3.Connection, touched: set[tuple[int, int]]
) -> None:
    conn.execute(_CREATE_TOUCHED)
    conn.execute(f"DELETE FROM {_TOUCHED}")
    _insert_rows(
        conn,
        f"INSERT INTO {_TOUCHED} (level, metric_id, bucket) VALUES ",
        f"({BUCKET_MIN_LEVEL}, ?, ?)",
        sorted(touched),
    )
    conn.execute(_REBUILD_POINT_LEVEL)
    for level in range(BUCKET_MIN_LEVEL + 1, BUCKET_MAX_LEVEL + 1):
        conn.execute(_TOUCH_PARENTS, (level,))
        conn.execute(_REBUILD_UPPER_LEVEL, (level,))


_CachedIds = tuple[sqlite3.Connection, dict[str, int]]


def _is_point(row: PendingRow) -> bool:
    return row[0] == METRIC_POINT_SQL


def _point_key(row: PendingRow) -> tuple[int, int]:
    return row[1][0], row[1][1]


def _points_in_key_order(rows: list[PendingRow]) -> list[PendingRow]:
    """Sorts each run of point rows by `(metric_id, step)`, keeping other rows in place.

    A wide batch puts each metric's points on their own pages; inserted in key order, a
    flush reads and writes each page once. The sort is stable, so the last write of a
    step still wins.
    """
    ordered: list[PendingRow] = []
    for is_point, run in groupby(rows, key=_is_point):
        if is_point:
            ordered.extend(sorted(run, key=_point_key))
        else:
            ordered.extend(run)
    return ordered


class MetricWriteHook:
    """Resolves metric keys to ids and keeps the buckets of a write buffer's flushes.

    Ids are cached once committed, for the connection they were read on: another
    process may delete and re-create the database, which only a new connection sees.
    The write buffer also drops a database's cache when it is deleted or created
    again, and every cache after a fork.
    """

    def __init__(self) -> None:
        # The connection is held, so a new one can never reuse its identity.
        self._ids: dict[str, _CachedIds] = {}
        self._uncommitted: dict[str, _CachedIds] = {}
        self._batch_keys: dict[str, BatchKeys] = {}

    def cached_ids(self, conn: sqlite3.Connection, db_path: str) -> dict[str, int]:
        cached = self._ids.get(db_path)
        return cached[1] if cached is not None and cached[0] is conn else {}

    def batch_keys(self, db_path: str) -> BatchKeys | None:
        return self._batch_keys.get(db_path)

    def prepare(
        self, conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> list[PendingRow]:
        known = self.cached_ids(conn, db_path)
        keys = {params[0] for sql, params in rows if sql == METRIC_POINT_SQL}
        if keys:
            self._batch_keys[db_path] = BatchKeys(
                count=len(keys), mean_length=sum(map(len, keys)) // len(keys)
            )
        else:
            self._batch_keys.pop(db_path, None)
        missing = keys.difference(known)
        fresh = self._register_keys(conn, missing) if missing else {}
        self._uncommitted[db_path] = (conn, fresh)
        ids = known | fresh if fresh else known
        prepared = [
            (sql, (ids[params[0]], *params[1:]))
            if sql == METRIC_POINT_SQL
            else (sql, params)
            for sql, params in rows
        ]
        return _points_in_key_order(prepared) if len(keys) > 1 else prepared

    @staticmethod
    def _register_keys(conn: sqlite3.Connection, keys: set[str]) -> dict[str, int]:
        ordered = sorted(keys)
        conn.executemany(
            "INSERT OR IGNORE INTO metric_keys (key) VALUES (?)",
            [(key,) for key in ordered],
        )
        ids: dict[str, int] = {}
        for start in range(0, len(ordered), _KEY_LOOKUP_CHUNK):
            chunk = ordered[start : start + _KEY_LOOKUP_CHUNK]
            placeholders = ", ".join("?" * len(chunk))
            ids.update(
                (key, metric_id)
                for metric_id, key in conn.execute(
                    f"SELECT id, key FROM metric_keys WHERE key IN ({placeholders})",
                    chunk,
                )
            )
        return ids

    @staticmethod
    def execute_many(
        conn: sqlite3.Connection, sql: str, params: list[tuple[Any, ...]]
    ) -> None:
        if sql == METRIC_POINT_SQL:
            _insert_rows(conn, _POINT_INSERT, "(?, ?, ?, ?)", params)
        else:
            conn.executemany(sql, params)

    @staticmethod
    def before_commit(
        conn: sqlite3.Connection, db_path: str, rows: list[PendingRow]
    ) -> None:
        shift = 2 * BUCKET_MIN_LEVEL
        touched = {
            (params[0], params[1] >> shift)
            for sql, params in rows
            if sql == METRIC_POINT_SQL
        }
        if touched:
            refresh_buckets(conn, touched)

    def after_commit(self, db_path: str) -> None:
        uncommitted = self._uncommitted.pop(db_path, None)
        if uncommitted is None:
            return
        conn, fresh = uncommitted
        known = self.cached_ids(conn, db_path)
        if not known:
            self._ids[db_path] = (conn, known)
        known.update(fresh)

    def forget(self, db_path: str) -> None:
        self._ids.pop(db_path, None)
        self._uncommitted.pop(db_path, None)
        self._batch_keys.pop(db_path, None)

    def forget_all(self) -> None:
        self._ids = {}
        self._uncommitted = {}
        self._batch_keys = {}


def _clamp_step(step: int) -> int:
    return min(max(step, _INT64_MIN), _INT64_MAX)


# Released revisions all have the PRIMARY KEY (key, step) autoindex. Seeks on it need
# BINARY order on both columns; a partial index may lack rows.
_LEGACY_KEY_STEP_INDEX = """
SELECT il.name FROM pragma_index_list('dynamic_metrics') il
WHERE il.partial = 0
  AND EXISTS (SELECT 1 FROM pragma_index_xinfo(il.name) x
              WHERE x.seqno = 0 AND x.name = 'key' AND x.coll = 'BINARY')
  AND EXISTS (SELECT 1 FROM pragma_index_xinfo(il.name) x
              WHERE x.seqno = 1 AND x.name = 'step' AND x.coll = 'BINARY')
ORDER BY il."unique" DESC, il.name LIMIT 1
"""


def _legacy_seek_queries(index: str) -> tuple[str, str]:
    """Catalog rows (key, first_step, last_step, skipped) and the non-text key count.

    SQLite orders NULL < numbers < text < BLOB, so `key >= '' AND key < x''` holds the
    text keys, `step < ''` the numeric steps and `step >= ''` the text and BLOB steps:
    every subquery is an index range, and the keys come from a skip scan.
    """
    quoted = index.replace('"', '""')
    table = f'dynamic_metrics INDEXED BY "{quoted}"'
    integer_steps = (
        f"SELECT step FROM {table} WHERE key = k.key AND step < '' "
        "AND typeof(step) = 'integer' ORDER BY step"
    )
    catalog = f"""
        WITH RECURSIVE k(key) AS (
            SELECT (SELECT key FROM {table} WHERE key >= '' AND key < x''
                    ORDER BY key LIMIT 1)
            UNION ALL
            SELECT (SELECT key FROM {table} WHERE key > k.key AND key < x''
                    ORDER BY key LIMIT 1)
            FROM k WHERE k.key IS NOT NULL
        )
        SELECT key, ({integer_steps} LIMIT 1), ({integer_steps} DESC LIMIT 1),
               (SELECT count(*) FROM {table} WHERE key = k.key AND step IS NULL)
               + (SELECT count(*) FROM {table} WHERE key = k.key AND step >= '')
        FROM k WHERE key IS NOT NULL
        """
    non_text_keys = f"""
        SELECT (SELECT count(*) FROM {table} WHERE key IS NULL)
               + (SELECT count(*) FROM {table} WHERE key < '')
               + (SELECT count(*) FROM {table} WHERE key >= x'')
        """
    return catalog, non_text_keys


def _legacy_catalog(conn: sqlite3.Connection) -> tuple[list[MetricSummary], int]:
    """Revisions 0-2: count, min and max are None, as only the index is read.

    Fractional REAL steps are left out of the steps but not counted as skipped;
    finding them needs a full scan.
    """
    index = conn.execute(_LEGACY_KEY_STEP_INDEX).fetchone()
    if index is None:
        return _legacy_scan_catalog(conn)
    catalog_sql, non_text_keys_sql = _legacy_seek_queries(index[0])
    skipped_rows: int = conn.execute(non_text_keys_sql).fetchone()[0]
    metrics: list[MetricSummary] = []
    for key, first_step, last_step, skipped in conn.execute(catalog_sql):
        skipped_rows += skipped
        if first_step is not None:
            metrics.append(MetricSummary(key, first_step, last_step, None, None, None))
    return metrics, skipped_rows


def _legacy_scan_catalog(conn: sqlite3.Connection) -> tuple[list[MetricSummary], int]:
    rows = conn.execute(
        f"""
        SELECT key, min(step), max(step), count(*),
               min(CASE WHEN {NUMERIC_SQL.format("value")} THEN value END),
               max(CASE WHEN {NUMERIC_SQL.format("value")} THEN value END)
        FROM dynamic_metrics
        WHERE {_LEGACY_ROW}
        GROUP BY key
        ORDER BY key
        """
    ).fetchall()
    skipped_rows: int = conn.execute(
        f"SELECT count(*) FROM dynamic_metrics WHERE NOT ({_LEGACY_ROW})"
    ).fetchone()[0]
    return [MetricSummary(*row) for row in rows], skipped_rows


def fetch_metric_catalog(
    conn: sqlite3.Connection, schema: ExperimentSchema
) -> MetricCatalog:
    # The top stored level holds a few rows per metric and is contiguous in the
    # level-first key, so the catalog reads a handful of pages at any size.
    if schema.has_metric_points and schema.bucket_max_level is not None:
        rows = conn.execute(
            """
            SELECT k.key, min(b.first_step), max(b.last_step), sum(b.count),
                   min(b.min), max(b.max)
            FROM metric_buckets b JOIN metric_keys k ON k.id = b.metric_id
            WHERE b.level = ?
            GROUP BY b.metric_id
            ORDER BY k.key
            """,
            (schema.bucket_max_level,),
        ).fetchall()
        metrics = [MetricSummary(*row) for row in rows]
        skipped_rows = 0
    else:
        metrics, skipped_rows = _legacy_catalog(conn)
    return MetricCatalog(
        revision=schema.revision,
        metrics=metrics,
        bucket_min_level=schema.bucket_min_level if schema.has_metric_points else None,
        bucket_max_level=schema.bucket_max_level if schema.has_metric_points else None,
        skipped_rows=skipped_rows,
    )


def _metric_id(conn: sqlite3.Connection, key: str) -> int | None:
    row = conn.execute("SELECT id FROM metric_keys WHERE key = ?", (key,)).fetchone()
    return None if row is None else row[0]


def _metric_span(
    conn: sqlite3.Connection, schema: ExperimentSchema, key: str, metric_id: int | None
) -> tuple[int, int] | None:
    # One seek per subquery: a min() and a max() in one SELECT read every point.
    param: int | str
    if schema.has_metric_points:
        if metric_id is None:
            return None
        source, param = "metric_points WHERE metric_id = ?1", metric_id
    else:
        # SQLite orders numbers before text and BLOBs, so `< ''` keeps the index range
        # to numeric steps; numpy BLOB steps would otherwise all be scanned past.
        source, param = (
            "dynamic_metrics WHERE key = ?1 AND step < '' AND typeof(step) = 'integer'",
            key,
        )
    row = conn.execute(
        f"SELECT (SELECT step FROM {source} ORDER BY step LIMIT 1), "
        f"(SELECT step FROM {source} ORDER BY step DESC LIMIT 1)",
        (param,),
    ).fetchone()
    return None if row[0] is None else (row[0], row[1])


def _bucket_source_query(schema: ExperimentSchema, level: int) -> tuple[str, str]:
    """Returns the query for `level` and the unit its bounds are given in."""
    min_level, max_level = schema.bucket_min_level, schema.bucket_max_level
    if schema.has_metric_points and min_level is not None and max_level is not None:
        if min_level <= level <= max_level:
            return (
                """
                SELECT bucket, first_step, last_step, count, finite_count, min, max, sum
                FROM metric_buckets
                WHERE level = :level AND metric_id = :metric_id
                  AND bucket BETWEEN :low AND :high
                ORDER BY bucket LIMIT :limit
                """,
                "bucket",
            )
        if level > max_level:
            return (
                f"""
                SELECT c.bucket >> :coarsen AS b, min(c.first_step), max(c.last_step),
                       sum(c.count), sum(c.finite_count), min(c.min), max(c.max), sum(c.sum)
                FROM metric_buckets c
                WHERE c.level = {max_level} AND c.metric_id = :metric_id
                  AND c.bucket BETWEEN :low AND :high
                GROUP BY b ORDER BY b LIMIT :limit
                """,
                "top",
            )
    source = (
        "metric_points WHERE metric_id = :metric_id"
        if schema.has_metric_points
        else "dynamic_metrics WHERE key = :key AND typeof(step) = 'integer'"
    )
    return (
        f"""
        SELECT step >> :shift AS b, min(step), max(step), {_value_aggregates("value")}
        FROM {source} AND step BETWEEN :low AND :high
        GROUP BY b ORDER BY b LIMIT :limit
        """,
        "step",
    )


def fetch_metric_buckets(
    conn: sqlite3.Connection,
    schema: ExperimentSchema,
    key: str,
    level: int,
    start_step: int | None = None,
    end_step: int | None = None,
) -> MetricBuckets:
    if (
        isinstance(level, bool)
        or not isinstance(level, int)
        or not 0 <= level <= MAX_BUCKET_LEVEL
    ):
        raise InvalidBucketLevelError(level, MAX_BUCKET_LEVEL)
    metric_id = _metric_id(conn, key) if schema.has_metric_points else None
    span = _metric_span(conn, schema, key, metric_id)
    if span is None:
        return MetricBuckets(key=key, level=level, first_step=None, last_step=None)
    first_step, last_step = span
    result = MetricBuckets(
        key=key, level=level, first_step=first_step, last_step=last_step
    )
    start = first_step if start_step is None else start_step
    end = last_step if end_step is None else end_step
    if start > end or start > _INT64_MAX or end < _INT64_MIN:
        return result
    start, end = _clamp_step(start), _clamp_step(end)

    shift = 2 * level
    # Bounds widened to whole buckets: a bucket at the edge of the range is returned
    # in full. `>>` is an arithmetic shift, a floor division also for negative steps.
    low = _clamp_step((start >> shift) << shift)
    high = _clamp_step((((end >> shift) + 1) << shift) - 1)
    query, unit = _bucket_source_query(schema, level)
    params: dict[str, int | str | None] = {
        "level": level,
        "metric_id": metric_id,
        "key": key,
        "shift": shift,
        "limit": MAX_RETURNED_BUCKETS + 1,
    }
    if unit == "bucket":
        params.update(low=start >> shift, high=end >> shift)
    elif unit == "top":
        top_shift = 2 * (schema.bucket_max_level or 0)
        params.update(
            low=low >> top_shift, high=high >> top_shift, coarsen=shift - top_shift
        )
    else:
        params.update(low=low, high=high)
    rows = conn.execute(query, params).fetchall()
    if len(rows) > MAX_RETURNED_BUCKETS:
        raise TooManyBucketsError(MAX_RETURNED_BUCKETS)
    result.buckets = [MetricBucket(*row) for row in rows]
    return result
