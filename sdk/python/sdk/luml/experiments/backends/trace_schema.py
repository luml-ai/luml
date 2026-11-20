"""Trace and eval read indexes of experiment schema revision 3, shared by its migration
and the snapshot export.

Each index covers the columns of one structural read, so the read never touches the
payload columns. Released SDKs keep them up to date like any index.
"""

import sqlite3

TRACE_EVAL_INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "spans_structure": (
        "spans",
        (
            "trace_id",
            "start_time_unix_nano",
            "span_id",
            "parent_span_id",
            "end_time_unix_nano",
            "status_code",
            "name",
            "kind",
            "dfs_span_type",
            "created_at",
            "trace_flags",
        ),
    ),
    "evals_list": ("evals", ("dataset_id", "created_at", "id", "updated_at", "scores")),
    "eval_traces_bridge_trace": ("eval_traces_bridge", ("trace_id", "eval_id")),
    "eval_traces_bridge_eval": (
        "eval_traces_bridge",
        ("eval_id", "eval_dataset_id", "trace_id"),
    ),
    "span_annotations_span": ("span_annotations", ("trace_id", "span_id")),
    "eval_annotations_eval": ("eval_annotations", ("dataset_id", "eval_id")),
}


def table_columns(
    conn: sqlite3.Connection, schema: str = "main"
) -> dict[str, set[str]]:
    tables = [
        row[0]
        for row in conn.execute(
            f"SELECT name FROM {schema}.sqlite_master WHERE type = 'table'"
        )
    ]
    return {
        table: {
            row[1] for row in conn.execute(f'PRAGMA {schema}.table_info("{table}")')
        }
        for table in tables
    }


def create_trace_eval_indexes(conn: sqlite3.Connection, schema: str = "main") -> None:
    # Stores of the first releases lack the annotation tables, though they are
    # recorded at revision 1.
    columns = table_columns(conn, schema)
    for name, (table, indexed) in TRACE_EVAL_INDEXES.items():
        if set(indexed) <= columns.get(table, set()):
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {schema}.{name} "
                f"ON {table}({', '.join(indexed)})"
            )
