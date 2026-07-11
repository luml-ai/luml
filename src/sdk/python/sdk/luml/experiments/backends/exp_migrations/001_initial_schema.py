# flake8: noqa: E501
import sqlite3

VERSION = 1
DESCRIPTION = "Initial experiment schema"

_CREATE_STATIC = """
    CREATE TABLE IF NOT EXISTS static_params (
        key TEXT PRIMARY KEY,
        value TEXT,
        value_type TEXT
    )
"""

_CREATE_DYNAMIC = """
    CREATE TABLE IF NOT EXISTS dynamic_metrics (
        key TEXT,
        value REAL,
        step INTEGER,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (key, step)
    )
"""

_CREATE_ATTACHMENTS = """
    CREATE TABLE IF NOT EXISTS attachments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        file_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_CREATE_SPANS = """
    CREATE TABLE IF NOT EXISTS spans (
        trace_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        parent_span_id TEXT,
        name TEXT NOT NULL,
        kind INTEGER,
        dfs_span_type INTEGER NOT NULL DEFAULT 0,
        start_time_unix_nano BIGINT NOT NULL,
        end_time_unix_nano BIGINT NOT NULL,
        status_code INTEGER,
        status_message TEXT,
        attributes TEXT,
        events TEXT,
        links TEXT,
        trace_flags INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (trace_id, span_id)
    )
"""

_CREATE_EVALS = """
    CREATE TABLE IF NOT EXISTS evals (
        id TEXT NOT NULL,
        dataset_id TEXT NOT NULL,
        inputs TEXT NOT NULL,
        outputs TEXT,
        refs TEXT,
        scores TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (dataset_id, id)
    )
"""

_CREATE_EVAL_TRACES_BRIDGE = """
    CREATE TABLE IF NOT EXISTS eval_traces_bridge (
        id TEXT PRIMARY KEY,
        eval_dataset_id TEXT NOT NULL,
        eval_id TEXT NOT NULL,
        trace_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

_CREATE_EVAL_ANNOTATIONS = """
    CREATE TABLE IF NOT EXISTS eval_annotations (
        id TEXT PRIMARY KEY,
        dataset_id TEXT NOT NULL,
        eval_id TEXT NOT NULL,
        name TEXT NOT NULL,
        annotation_kind TEXT NOT NULL CHECK(annotation_kind IN ('feedback', 'expectation')),
        value_type TEXT NOT NULL CHECK(value_type IN ('int', 'bool', 'string')),
        value TEXT NOT NULL,
        user TEXT NOT NULL,
        rationale TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dataset_id, eval_id) REFERENCES evals(dataset_id, id)
    )
"""

_CREATE_SPAN_ANNOTATIONS = """
    CREATE TABLE IF NOT EXISTS span_annotations (
        id TEXT PRIMARY KEY,
        trace_id TEXT NOT NULL,
        span_id TEXT NOT NULL,
        name TEXT NOT NULL,
        annotation_kind TEXT NOT NULL CHECK(annotation_kind IN ('feedback', 'expectation')),
        value_type TEXT NOT NULL CHECK(value_type IN ('int', 'bool', 'string')),
        value TEXT NOT NULL,
        user TEXT NOT NULL,
        rationale TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (trace_id, span_id) REFERENCES spans(trace_id, span_id)
    )
"""


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(_CREATE_STATIC)
    cursor.execute(_CREATE_DYNAMIC)
    cursor.execute(_CREATE_ATTACHMENTS)
    cursor.execute(_CREATE_SPANS)
    cursor.execute(_CREATE_EVALS)
    cursor.execute(_CREATE_EVAL_TRACES_BRIDGE)
    cursor.execute(_CREATE_EVAL_ANNOTATIONS)
    cursor.execute(_CREATE_SPAN_ANNOTATIONS)
    cursor.execute("PRAGMA user_version = 1")


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS span_annotations")
    cursor.execute("DROP TABLE IF EXISTS eval_annotations")
    cursor.execute("DROP TABLE IF EXISTS eval_traces_bridge")
    cursor.execute("DROP TABLE IF EXISTS evals")
    cursor.execute("DROP TABLE IF EXISTS spans")
    cursor.execute("DROP TABLE IF EXISTS attachments")
    cursor.execute("DROP TABLE IF EXISTS dynamic_metrics")
    cursor.execute("DROP TABLE IF EXISTS static_params")
    cursor.execute("PRAGMA user_version = 0")
