"""What the platform viewer computes on read from the unfiltered tables, in Python and
without the export SQL, to check the snapshot summary tables against."""

import json
import math
import sqlite3
from collections import defaultdict
from typing import Any

from luml.experiments.backends._snapshot_summaries import SUMMARY_TABLES

EVAL_JSON_COLUMNS = ("inputs", "outputs", "refs", "scores", "metadata")
KEY_CATALOG_TABLES = ("snapshot_span_attribute_keys", "snapshot_eval_column_keys")
# SQLITE_TYPE_MAP of the viewer; any other json_each type reads as unknown.
VIEWER_TYPES = {
    "text": "string",
    "integer": "number",
    "real": "number",
    "true": "boolean",
    "false": "boolean",
}


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not JSON")


def viewer_parse(text: object) -> object:
    """JSON.parse of the viewer's safeParse: the raw value when it is not JSON."""
    if not isinstance(text, str):
        return text
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        return text


def json5_type(value: object) -> str:
    """The json_each type of a parsed value; SQLite reads the JSON5 NaN as null."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    if isinstance(value, str):
        return "text"
    return "array" if isinstance(value, list) else "object"


def _json5_items(text: object) -> list[tuple[str, object]]:
    """The top-level (key, value) pairs json_each yields; Python's json reads the NaN
    and Infinity of json.dumps as JSON5 does. Text no reader can parse has none."""
    if not isinstance(text, str):
        return []
    try:
        value = json.loads(text)
    except ValueError:
        return []
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, list):
        return [(str(index), item) for index, item in enumerate(value)]
    return []


def trace_summaries(conn: sqlite3.Connection) -> dict[str, tuple[Any, ...]]:
    rows = conn.execute(
        "SELECT trace_id, start_time_unix_nano, end_time_unix_nano, parent_span_id, "
        "status_code, created_at FROM spans"
    ).fetchall()
    by_trace: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        by_trace[row[0]].append(row)
    summaries = {}
    for trace_id, spans in by_trace.items():
        start = min(span[1] for span in spans)
        end = max(span[2] for span in spans)
        root_statuses = [s[4] for s in spans if s[3] is None and s[4] is not None]
        root_status = max(root_statuses) if root_statuses else None
        state = (
            3 if root_status is None else root_status if root_status in (1, 2) else 0
        )
        created = [span[5] for span in spans if span[5] is not None]
        summaries[trace_id] = (
            start,
            end,
            end - start,
            len(spans),
            state,
            min(created) if created else None,
        )
    return summaries


def score_stats(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[int, float]]:
    """Per (dataset, key): how many values the viewer averages, and their sum."""
    stats: dict[tuple[str, str], list[float]] = defaultdict(list)
    for dataset_id, text in conn.execute(
        "SELECT dataset_id, scores FROM evals WHERE scores IS NOT NULL"
    ):
        scores = viewer_parse(text)
        if isinstance(scores, list):
            scores = {str(index): value for index, value in enumerate(scores)}
        if not isinstance(scores, dict):
            continue
        for key, value in scores.items():
            if isinstance(value, int | float):
                stats[dataset_id, key].append(float(value))
    return {key: (len(values), math.fsum(values)) for key, values in stats.items()}


def span_attribute_types(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Every json_each type each attribute key has: the viewer shows any one of them."""
    types: dict[str, set[str]] = defaultdict(set)
    for (text,) in conn.execute(
        "SELECT attributes FROM spans WHERE attributes IS NOT NULL"
    ):
        for key, value in _json5_items(text):
            types[key].add(json5_type(value))
    return dict(types)


def eval_column_types(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str, str], set[str]]:
    types: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for column in EVAL_JSON_COLUMNS:
        for dataset_id, text in conn.execute(
            f"SELECT dataset_id, {column} FROM evals WHERE {column} IS NOT NULL"
        ):
            for key, value in _json5_items(text):
                types[dataset_id, column, key].add(json5_type(value))
    return dict(types)


def exports_key_catalogs() -> bool:
    """Whether an export on this SQLite builds the key catalogs: only from 3.45 does
    json_valid accept the JSON5 that the viewer's json_each reads."""
    return sqlite3.sqlite_version_info >= (3, 45, 0)


def exported_summary_tables() -> set[str]:
    if exports_key_catalogs():
        return set(SUMMARY_TABLES)
    return set(SUMMARY_TABLES) - set(KEY_CATALOG_TABLES)


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in rows}


def stored_summaries(conn: sqlite3.Connection) -> dict[str, Any]:
    """The summary tables; the key catalogs only where the snapshot has them."""
    stored: dict[str, Any] = {
        "traces": {
            row[0]: tuple(row[1:])
            for row in conn.execute("SELECT * FROM snapshot_trace_summaries")
        },
        "scores": {
            (row[0], row[1]): (row[2], row[3])
            for row in conn.execute("SELECT * FROM snapshot_eval_score_stats")
        },
    }
    if set(KEY_CATALOG_TABLES) <= _tables(conn):
        stored["attributes"] = dict(
            conn.execute("SELECT key, type FROM snapshot_span_attribute_keys")
        )
        stored["columns"] = {
            (row[0], row[1], row[2]): row[3]
            for row in conn.execute("SELECT * FROM snapshot_eval_column_keys")
        }
    return stored


def assert_summaries_match_reads(conn: sqlite3.Connection, key_catalogs: bool) -> None:
    """`key_catalogs`: the snapshot must have both key catalogs, or else neither."""
    stored = stored_summaries(conn)
    assert stored["traces"] == trace_summaries(conn)
    expected_scores = score_stats(conn)
    assert stored["scores"].keys() == expected_scores.keys()
    for key, (count, total) in expected_scores.items():
        assert stored["scores"][key][0] == count, key
        assert math.isclose(stored["scores"][key][1], total, rel_tol=1e-12), key
    if not key_catalogs:
        assert not set(KEY_CATALOG_TABLES) & _tables(conn)
        return
    attribute_types = span_attribute_types(conn)
    assert stored["attributes"].keys() == attribute_types.keys()
    for key, kind in stored["attributes"].items():
        assert kind in attribute_types[key], key
    column_types = eval_column_types(conn)
    assert stored["columns"].keys() == column_types.keys()
    for key, kind in stored["columns"].items():
        assert kind in column_types[key], key
