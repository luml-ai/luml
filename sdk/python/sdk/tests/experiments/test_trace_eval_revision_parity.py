"""Every trace and eval read gives the same result, in the same order, on a revision 2
store and on a revision 3 store holding the same rows.

Rows are inserted so that table order differs from every index order: ids are
shuffled, timestamps tie, eval ids repeat across datasets and evals and traces have
several links.
"""

import json
import sqlite3
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends.data_types import PaginatedResponse, TraceState
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import make_revision2_store, make_store

EXP_ID = "exp"
SAME_TIME = "2026-01-01 00:00:00"
LATER = "2026-01-02 00:00:00"

SPANS = [
    ("t2", "s9", None, 0, 50, 1, {"k": 1, "mixed": "text"}, LATER),
    ("t2", "s1", "s9", 10, 20, 2, {"k": 2.5}, LATER),
    ("t3", "s5", None, 0, 30, 2, {"mixed": 3}, SAME_TIME),
    ("t3", "s2", "s5", 0, 30, None, None, SAME_TIME),
    ("t1", "s7", None, 5, 35, 1, {"k": "x", "mixed": True}, SAME_TIME),
    ("t1", "s3", "s7", 5, 20, 0, {"k": 0}, SAME_TIME),
    ("t1", "s4", "s7", 5, 20, 1, {}, SAME_TIME),
    ("t4", "s8", "missing", 1, 31, 1, {"k": 7}, SAME_TIME),
]

EVALS = [
    ("e3", "d2", {"q": 3}, {"acc": 0.1, "f1": 1, "g": "x", "h": 2}, SAME_TIME),
    ("e1", "d2", {"q": "one"}, {"acc": 0.2, "f1": "n/a", "h": "y"}, LATER),
    ("e2", "d1", {"q": 2}, {"acc": 0.3, "f1": 0.5, "g": 1}, SAME_TIME),
    ("e1", "d1", {"q": 1}, {"acc": 1e16, "f1": 2}, SAME_TIME),
    ("e3", "d1", {"q": 3}, {"acc": 0.1}, LATER),
    ("e4", "d1", {"q": 4}, None, SAME_TIME),
]

LINKS = [
    ("b1", "d1", "e2", "t2"),
    ("b7", "d1", "e2", "t1"),
    ("b3", "d2", "e3", "t3"),
    ("b5", "d1", "e1", "t3"),
    ("b2", "d1", "e1", "t1"),
    ("b9", "d2", "e1", "t2"),
    ("b4", "d1", "e1", "t2"),
]

EVAL_ANNOTATIONS = [
    ("a2", "d1", "e2", "answer", "expectation", "bool", "true"),
    ("a9", "d1", "e1", "quality", "feedback", "bool", "true"),
    ("a1", "d1", "e1", "quality", "feedback", "bool", "false"),
    ("a5", "d2", "e1", "quality", "feedback", "bool", "true"),
    ("a3", "d1", "e1", "answer", "expectation", "string", "bird"),
    ("a7", "d1", "e1", "answer", "expectation", "int", "4"),
]

SPAN_ANNOTATIONS = [
    ("n8", "t1", "s3", "ok", "feedback", "bool", "true"),
    ("n2", "t1", "s3", "ok", "feedback", "bool", "false"),
    ("n5", "t1", "s7", "ok", "feedback", "int", "3"),
    ("n1", "t3", "s5", "label", "expectation", "string", "cat"),
    ("n6", "t3", "s2", "label", "expectation", "int", "2"),
    ("n3", "t1", "s3", "label", "expectation", "string", "dog"),
]


def _insert_rows(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO spans (trace_id, span_id, parent_span_id, name, kind, "
        "start_time_unix_nano, end_time_unix_nano, status_code, status_message, "
        "attributes, events, links, trace_flags, created_at) "
        "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, NULL, 1, ?)",
        [
            (
                trace_id,
                span_id,
                parent,
                f"op-{span_id}",
                start,
                end,
                status,
                "boom" if status == 2 else None,
                None if attributes is None else json.dumps(attributes),
                json.dumps([{"name": "event"}]) if span_id == "s1" else None,
                created_at,
            )
            for (
                trace_id,
                span_id,
                parent,
                start,
                end,
                status,
                attributes,
                created_at,
            ) in SPANS
        ],
    )
    conn.executemany(
        "INSERT INTO evals (id, dataset_id, inputs, outputs, scores, metadata, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                eval_id,
                dataset_id,
                json.dumps(inputs),
                json.dumps({"a": eval_id}),
                None if scores is None else json.dumps(scores),
                json.dumps({"source": dataset_id}),
                created_at,
                created_at,
            )
            for eval_id, dataset_id, inputs, scores, created_at in EVALS
        ],
    )
    conn.executemany(
        "INSERT INTO eval_traces_bridge (id, eval_dataset_id, eval_id, trace_id, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        [(*link, SAME_TIME) for link in LINKS],
    )
    for table, rows in (
        ("eval_annotations (id, dataset_id, eval_id", EVAL_ANNOTATIONS),
        ("span_annotations (id, trace_id, span_id", SPAN_ANNOTATIONS),
    ):
        conn.executemany(
            f"INSERT INTO {table}, name, annotation_kind, value_type, value, user, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'user', ?)",
            [(*row, SAME_TIME) for row in rows],
        )
    conn.commit()
    conn.close()


def _revision(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture(scope="module")
def stores(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[SQLiteBackend, SQLiteBackend]]:
    root = tmp_path_factory.mktemp("parity")
    old_db = make_revision2_store(root / "revision2", EXP_ID)
    make_store(root / "revision3", EXP_ID)
    new_db = root / "revision3" / EXP_ID / "exp.db"
    for db_path in (old_db, new_db):
        _insert_rows(db_path)
    assert (_revision(old_db), _revision(new_db)) == (2, 4)
    old = SQLiteBackend(str(root / "revision2"), flush_interval=0)
    new = SQLiteBackend(str(root / "revision3"), flush_interval=0)
    yield old, new
    old.close()
    new.close()


Kwargs = dict[str, Any]
Read = Callable[[SQLiteBackend], object]


def _pages(
    list_page: Callable[[str | None], PaginatedResponse[Any]],
) -> list[list[Any]]:
    pages = []
    cursor = None
    while True:
        page = list_page(cursor)
        pages.append(page.items)
        cursor = page.cursor
        if cursor is None:
            return pages


def _trace_pages(kwargs: Kwargs, backend: SQLiteBackend) -> object:
    return _pages(
        lambda cursor: backend.get_experiment_traces(
            EXP_ID, limit=2, cursor_str=cursor, **kwargs
        )
    )


def _eval_pages(kwargs: Kwargs, backend: SQLiteBackend) -> object:
    return _pages(
        lambda cursor: backend.get_experiment_evals(
            EXP_ID, limit=2, cursor_str=cursor, **kwargs
        )
    )


def _batch_eval_pages(kwargs: Kwargs, backend: SQLiteBackend) -> object:
    return _pages(
        lambda cursor: backend.get_batch_experiment_evals(
            [EXP_ID], limit=2, cursor_str=cursor, **kwargs
        )
    )


def _all_traces(kwargs: Kwargs, backend: SQLiteBackend) -> object:
    return backend.get_experiment_traces_all(EXP_ID, **kwargs)


def _all_evals(kwargs: Kwargs, backend: SQLiteBackend) -> object:
    return backend.get_experiment_evals_all(EXP_ID, **kwargs)


def _average_scores(kwargs: Kwargs, backend: SQLiteBackend) -> object:
    return backend.get_evals_average_scores(EXP_ID, **kwargs)


def _trace(trace_id: str, backend: SQLiteBackend) -> object:
    return (
        backend.get_trace(EXP_ID, trace_id),
        backend.get_trace_structure(EXP_ID, trace_id),
        backend.get_trace_annotation_summary(EXP_ID, trace_id),
    )


def _span(trace_id: str, span_id: str, backend: SQLiteBackend) -> object:
    return (
        backend.get_span(EXP_ID, trace_id, span_id),
        backend.get_span_annotations(EXP_ID, trace_id, span_id),
    )


def _eval(dataset_id: str, eval_id: str, backend: SQLiteBackend) -> object:
    return (
        backend.get_eval(EXP_ID, eval_id),
        backend.get_eval_annotations(EXP_ID, dataset_id, eval_id),
    )


def _eval_columns(dataset_id: str | None, backend: SQLiteBackend) -> object:
    return (
        backend.get_experiment_eval_columns(EXP_ID, dataset_id),
        backend.get_experiment_eval_typed_columns(EXP_ID, dataset_id),
        backend.get_eval_annotation_summary(EXP_ID, dataset_id or "d1"),
    )


def _experiment_wide(backend: SQLiteBackend) -> object:
    return (
        backend.get_experiment_trace_columns(EXP_ID),
        backend.get_experiment_trace_typed_columns(EXP_ID),
        backend.get_experiment_eval_dataset_ids(EXP_ID),
        [
            backend.resolve_evals_sort_column(EXP_ID, key)
            for key in ("created_at", "acc", "q", "a", "source")
        ],
        backend.get_all_traces_annotation_summary(EXP_ID),
        backend.get_traces_annotation_summaries(EXP_ID, ["t3", "t1", "t2"]),
        backend.get_evals_annotation_summaries(EXP_ID, ["e2", "e1", "e3"]),
    )


TRACE_IDS = sorted({span[0] for span in SPANS})
SPAN_KEYS = [(span[0], span[1]) for span in SPANS] + [("t1", "absent")]
EVAL_KEYS = sorted({(e[1], e[0]) for e in EVALS})
ORDERS = ("asc", "desc")
TRACE_SORTS = ("execution_time", "span_count", "created_at")
EVAL_SORTS: list[Kwargs] = [
    {"sort_by": "created_at"},
    {"sort_by": "updated_at"},
    {"sort_by": "dataset_id"},
    {"sort_by": "acc", "json_sort_column": "scores"},
    {"sort_by": "f1", "json_sort_column": "scores"},
    {"sort_by": "q", "json_sort_column": "inputs"},
]
EVAL_SELECTIONS: list[Kwargs] = [
    {},
    {"dataset_id": "d1"},
    {"search": "e1"},
    {"filters": ["scores.acc > 0.15"]},
]
TRACE_SELECTIONS: list[Kwargs] = [
    {},
    {"search": "boom"},
    {"filters": ['evals = "e1"']},
    {"filters": ['attributes.k = "x"']},
    {"filters": ['annotations.feedback.ok = "true"']},
    {"states": [TraceState.OK, TraceState.ERROR]},
]
TRACE_LISTS: list[Kwargs] = [
    {"sort_by": sort_by, "order": order, **selection}
    for sort_by in TRACE_SORTS
    for order in ORDERS
    for selection in TRACE_SELECTIONS
]
EVAL_LISTS: list[Kwargs] = [
    {"order": order, **sort, **selection}
    for sort in EVAL_SORTS
    for order in ORDERS
    for selection in EVAL_SELECTIONS
]

READS: dict[str, Read] = {
    **{f"traces {k}": partial(_trace_pages, k) for k in TRACE_LISTS},
    **{f"all traces {k}": partial(_all_traces, k) for k in TRACE_LISTS},
    **{f"evals {k}": partial(_eval_pages, k) for k in EVAL_LISTS},
    **{f"all evals {k}": partial(_all_evals, k) for k in EVAL_LISTS},
    **{f"batch evals {k}": partial(_batch_eval_pages, k) for k in EVAL_SELECTIONS},
    **{f"average scores {k}": partial(_average_scores, k) for k in EVAL_SELECTIONS},
    **{f"trace {t}": partial(_trace, t) for t in [*TRACE_IDS, "absent"]},
    **{f"span {t} {s}": partial(_span, t, s) for t, s in SPAN_KEYS},
    **{f"eval {d} {e}": partial(_eval, d, e) for d, e in EVAL_KEYS},
    **{f"eval columns {d}": partial(_eval_columns, d) for d in (None, "d1", "d2")},
    "experiment wide": _experiment_wide,
}


@pytest.mark.parametrize("read", READS.values(), ids=READS.keys())
def test_revision_3_reads_match_revision_2(
    stores: tuple[SQLiteBackend, SQLiteBackend], read: Read
) -> None:
    old, new = stores
    assert read(new) == read(old)


def test_links_come_back_in_link_order(
    stores: tuple[SQLiteBackend, SQLiteBackend],
) -> None:
    for backend in stores:
        evaluation = backend.get_eval(EXP_ID, "e2")
        assert evaluation is not None
        assert evaluation.trace_ids == ["t2", "t1"]
        traces = {t.trace_id: t for t in backend.get_experiment_traces_all(EXP_ID)}
        assert traces["t1"].evals == ["e2", "e1"]
        assert traces["t3"].evals == ["e3", "e1"]
