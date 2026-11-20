"""Trace and eval summaries computed once at export, so that the browser reading a
published snapshot by range requests reads a few pages instead of whole tables.

Each table holds what the platform viewer computes on read from the unfiltered tables;
readers find them through `sqlite_master` and fall back to reading the tables. They are
built on the snapshot copy only: a live store never has them, so no writer, released
SDKs included, can leave them stale.
"""

import sqlite3

from luml.experiments.backends.trace_schema import (
    create_trace_eval_indexes,
    table_columns,
)

SUMMARY_TABLES = (
    "snapshot_trace_summaries",
    "snapshot_eval_score_stats",
    "snapshot_span_attribute_keys",
    "snapshot_eval_column_keys",
)
EVAL_JSON_COLUMNS = ("inputs", "outputs", "refs", "scores", "metadata")

_ROOT_STATUS = "MAX(CASE WHEN parent_span_id IS NULL THEN status_code END)"


def _builds_key_catalogs() -> bool:
    # The viewer's json_each reads JSON5, such as the NaN that json.dumps writes. Only
    # from 3.45 can json_valid accept it, so an older SQLite would drop such rows and
    # give a catalog that depends on the exporting machine; readers then fall back.
    return sqlite3.sqlite_version_info >= (3, 45, 0)


def _parsable(column: str) -> str:
    # A value json_each cannot parse would fail the whole export.
    return f"CASE WHEN json_valid({column}, 2) THEN {column} END"


def _trace_statements(s: str) -> list[str]:
    return [
        f"""CREATE TABLE {s}.snapshot_trace_summaries (
            trace_id TEXT PRIMARY KEY,
            start_time_unix_nano INTEGER NOT NULL,
            end_time_unix_nano INTEGER NOT NULL,
            execution_time INTEGER NOT NULL,
            span_count INTEGER NOT NULL,
            state INTEGER NOT NULL,
            created_at TEXT
        ) WITHOUT ROWID""",
        f"""INSERT INTO {s}.snapshot_trace_summaries
        SELECT trace_id, MIN(start_time_unix_nano), MAX(end_time_unix_nano),
            MAX(end_time_unix_nano) - MIN(start_time_unix_nano), COUNT(*),
            CASE
                WHEN {_ROOT_STATUS} IS NULL THEN 3
                WHEN {_ROOT_STATUS} = 2 THEN 2
                WHEN {_ROOT_STATUS} = 1 THEN 1
                ELSE 0
            END,
            MIN(created_at)
        FROM {s}.spans GROUP BY trace_id""",
        f"CREATE INDEX {s}.snapshot_trace_summaries_created "
        "ON snapshot_trace_summaries(created_at, trace_id)",
        f"CREATE INDEX {s}.snapshot_trace_summaries_duration "
        "ON snapshot_trace_summaries(execution_time, trace_id)",
        f"CREATE INDEX {s}.snapshot_trace_summaries_spans "
        "ON snapshot_trace_summaries(span_count, trace_id)",
    ]


def _span_key_statements(s: str) -> list[str]:
    return [
        f"""CREATE TABLE {s}.snapshot_span_attribute_keys (
            key TEXT PRIMARY KEY,
            type TEXT NOT NULL
        ) WITHOUT ROWID""",
        f"""INSERT INTO {s}.snapshot_span_attribute_keys
        SELECT CAST(je.key AS TEXT), je.type
        FROM {s}.spans, json_each({_parsable("spans.attributes")}) je
        WHERE spans.attributes IS NOT NULL AND je.key IS NOT NULL
        GROUP BY CAST(je.key AS TEXT)""",
    ]


def _score_statements(s: str) -> list[str]:
    return [
        f"""CREATE TABLE {s}.snapshot_eval_score_stats (
            dataset_id TEXT NOT NULL,
            score_key TEXT NOT NULL,
            count INTEGER NOT NULL,
            sum REAL,
            PRIMARY KEY (dataset_id, score_key)
        ) WITHOUT ROWID""",
        # The viewer parses scores with JSON.parse, which rejects NaN, so a row with NaN
        # counts for no key; it walks arrays by index too. TOTAL never overflows; a sum
        # is NULL only where Infinity meets -Infinity, as SQLite stores NaN as NULL.
        f"""INSERT INTO {s}.snapshot_eval_score_stats
        SELECT e.dataset_id, CAST(je.key AS TEXT), COUNT(*), TOTAL(je.value)
        FROM {s}.evals e,
            json_each(CASE WHEN json_valid(e.scores)
                AND json_type(e.scores) IN ('object', 'array') THEN e.scores END) je
        WHERE e.scores IS NOT NULL AND je.type IN ('integer', 'real', 'true', 'false')
        GROUP BY e.dataset_id, CAST(je.key AS TEXT)""",
    ]


def _eval_key_statements(s: str) -> list[str]:
    create = f"""CREATE TABLE {s}.snapshot_eval_column_keys (
        dataset_id TEXT NOT NULL,
        column_name TEXT NOT NULL,
        key TEXT NOT NULL,
        type TEXT NOT NULL,
        PRIMARY KEY (dataset_id, column_name, key)
    ) WITHOUT ROWID"""
    return [create] + [
        f"""INSERT INTO {s}.snapshot_eval_column_keys
        SELECT dataset_id, '{column}', CAST(je.key AS TEXT), je.type
        FROM {s}.evals, json_each({_parsable(f"evals.{column}")}) je
        WHERE evals.{column} IS NOT NULL AND je.key IS NOT NULL
        GROUP BY dataset_id, CAST(je.key AS TEXT)"""
        for column in EVAL_JSON_COLUMNS
    ]


def build_snapshot_summaries(conn: sqlite3.Connection, schema: str) -> None:
    """Adds the read indexes and the summary tables to the attached snapshot `schema`,
    in one transaction."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        create_trace_eval_indexes(conn, schema)
        tables = table_columns(conn, schema)
        catalogs = _builds_key_catalogs()
        statements: list[str] = []
        if "spans" in tables:
            statements += _trace_statements(schema)
            if catalogs:
                statements += _span_key_statements(schema)
        if "evals" in tables:
            statements += _score_statements(schema)
            if catalogs:
                statements += _eval_key_statements(schema)
        for statement in statements:
            conn.execute(statement)
    except BaseException:
        conn.rollback()
        raise
    conn.commit()
