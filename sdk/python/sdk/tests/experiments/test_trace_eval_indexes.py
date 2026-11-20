import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from luml.experiments.backends._search_utils import SearchTracesUtils
from luml.experiments.backends.data_types import AnnotationKind, AnnotationValueType
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.backends.trace_schema import TRACE_EVAL_INDEXES
from tests.experiments.metric_helpers import (
    LEGACY_INSERT,
    build_revision2_db,
    make_revision2_store,
)

EXP_ID = "exp"


def _indexes(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' "
            "AND name NOT LIKE 'sqlite_autoindex%'"
        )
    }


def test_migration_3_creates_the_indexes(tmp_path: Path) -> None:
    conn = sqlite3.connect(build_revision2_db(tmp_path / "exp.db"))
    conn.execute(LEGACY_INSERT, ("loss", 0.5, 0, "2026-01-02 03:04:05"))
    conn.commit()

    assert ExperimentMigrationRunner(conn).migrate(target_version=3) == [3]
    assert _indexes(conn) == set(TRACE_EVAL_INDEXES)
    assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    conn.close()


def test_migration_3_skips_indexes_of_tables_a_store_lacks(tmp_path: Path) -> None:
    conn = sqlite3.connect(build_revision2_db(tmp_path / "exp.db"))
    conn.execute("DROP TABLE span_annotations")
    conn.execute("DROP TABLE eval_annotations")
    conn.commit()

    assert ExperimentMigrationRunner(conn).migrate(target_version=3) == [3]
    assert _indexes(conn) == set(TRACE_EVAL_INDEXES) - {
        "span_annotations_span",
        "eval_annotations_eval",
    }
    conn.close()


def test_a_new_store_has_the_indexes(tmp_path: Path) -> None:
    backend = SQLiteBackend(str(tmp_path), flush_interval=0)
    backend.initialize_experiment(EXP_ID, name=EXP_ID)
    backend.close()

    conn = sqlite3.connect(tmp_path / EXP_ID / "exp.db")
    assert _indexes(conn) == set(TRACE_EVAL_INDEXES)
    conn.close()


def test_span_and_eval_writes_leave_a_revision_2_store_as_it_is(
    tmp_path: Path,
) -> None:
    db_path = make_revision2_store(tmp_path, EXP_ID)
    backend = SQLiteBackend(str(tmp_path), flush_interval=0)
    backend.log_span(EXP_ID, "t", "s", "span", 0, 1)
    backend.log_eval_sample(EXP_ID, "e", "d", {"q": 1}, scores={"a": 1.0})
    backend.link_eval_sample_to_trace(EXP_ID, "d", "e", "t")
    backend.log_span_annotation(
        EXP_ID,
        "t",
        "s",
        "ok",
        AnnotationKind.FEEDBACK,
        AnnotationValueType.BOOL,
        True,
        "user",
    )
    backend.get_trace_structure(EXP_ID, "t")
    backend.get_experiment_traces(EXP_ID)
    backend.close()

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone() == (2,)
    assert _indexes(conn) == set()
    conn.close()


@pytest.fixture
def populated(tmp_path: Path) -> tuple[SQLiteBackend, Path]:
    backend = SQLiteBackend(str(tmp_path), flush_interval=0)
    backend.initialize_experiment(EXP_ID, name=EXP_ID)
    for trace in range(20):
        for span in range(4):
            backend.log_span(
                EXP_ID,
                f"t{trace}",
                f"s{span}",
                "span",
                span,
                span + 10,
                parent_span_id=None if span == 0 else "s0",
                attributes={"payload": "x" * 200},
            )
    for sample in range(40):
        backend.log_eval_sample(
            EXP_ID, f"e{sample}", "d", {"q": sample}, scores={"acc": 0.5}
        )
    backend.link_eval_sample_to_trace(EXP_ID, "d", "e1", "t1")
    return backend, tmp_path / EXP_ID / "exp.db"


def _plans_of(
    backend: SQLiteBackend, db_path: Path, call: Callable[[], object], table: str
) -> list[str]:
    """The query plan of every statement on `table` that `call` runs."""
    statements: list[str] = []
    with backend.pool.get_connection(db_path) as conn:
        conn.set_trace_callback(statements.append)
    try:
        call()
    finally:
        with backend.pool.get_connection(db_path) as conn:
            conn.set_trace_callback(None)
    plans = []
    with backend.pool.get_connection(db_path) as conn:
        for sql in statements:
            if f"FROM {table}" in sql or f"FROM (SELECT * FROM {table}" in sql:
                plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
                plans.append("\n".join(row[3] for row in plan))
    assert plans, f"no statement on {table}"
    return plans


def test_structure_and_trace_list_read_only_the_structure_index(
    populated: tuple[SQLiteBackend, Path],
) -> None:
    backend, db_path = populated
    reads = {
        "structure": lambda: backend.get_trace_structure(EXP_ID, "t1"),
        "list": lambda: backend.get_experiment_traces(EXP_ID),
        "list by creation": lambda: backend.get_experiment_traces(
            EXP_ID, sort_by="created_at", order="asc"
        ),
        "all": lambda: backend.get_experiment_traces_all(EXP_ID),
    }
    for name, call in reads.items():
        plans = _plans_of(backend, db_path, call, "spans")
        assert "COVERING INDEX spans_structure" in plans[0], (name, plans)


def test_span_reads_one_row_by_its_key(
    populated: tuple[SQLiteBackend, Path],
) -> None:
    backend, db_path = populated
    plans = _plans_of(
        backend, db_path, lambda: backend.get_span(EXP_ID, "t1", "s2"), "spans"
    )
    assert "(trace_id=? AND span_id=?)" in plans[0]


def test_eval_pages_and_averages_read_the_eval_index(
    populated: tuple[SQLiteBackend, Path],
) -> None:
    backend, db_path = populated
    page = _plans_of(
        backend,
        db_path,
        lambda: backend.get_experiment_evals(EXP_ID, dataset_id="d"),
        "evals",
    )
    assert "USING INDEX evals_list (dataset_id=?)" in page[0]
    assert "TEMP B-TREE" not in page[0]
    for dataset_id in ("d", None):
        averages = _plans_of(
            backend,
            db_path,
            lambda dataset_id=dataset_id: backend.get_evals_average_scores(
                EXP_ID, dataset_id=dataset_id
            ),
            "evals",
        )
        assert "COVERING INDEX evals_list" in averages[0]


def test_eval_trace_links_read_their_indexes(
    populated: tuple[SQLiteBackend, Path],
) -> None:
    backend, db_path = populated
    plans = _plans_of(
        backend,
        db_path,
        lambda: backend.get_experiment_traces(EXP_ID),
        "eval_traces_bridge",
    )
    assert "COVERING INDEX eval_traces_bridge_trace (trace_id=?)" in plans[0]
    eval_page = _plans_of(
        backend,
        db_path,
        lambda: backend.get_experiment_evals(EXP_ID, dataset_id="d"),
        "eval_traces_bridge",
    )
    assert "COVERING INDEX eval_traces_bridge_eval (eval_id=?)" in eval_page[0]
    with backend.pool.get_connection(db_path) as conn:
        for trace_filter in ('evals = "e1"', 'evals != "e1"', 'evals IN ("e1", "e2")'):
            where, params = SearchTracesUtils.to_sql(trace_filter)
            plan = conn.execute(
                f"EXPLAIN QUERY PLAN SELECT trace_id FROM spans WHERE {where}", params
            ).fetchall()
            assert any(
                "COVERING INDEX eval_traces_bridge_eval (eval_id=?)" in row[3]
                for row in plan
            ), (trace_filter, plan)
    viewer_lookups = {
        "SELECT trace_id FROM eval_traces_bridge "
        "WHERE eval_dataset_id = 'd' AND eval_id = 'e1' ORDER BY rowid LIMIT 1": (
            "eval_traces_bridge_eval"
        ),
        "SELECT eval_id FROM eval_traces_bridge WHERE trace_id = 't1' "
        "ORDER BY rowid": "eval_traces_bridge_trace",
        "SELECT span_id, COUNT(*) FROM span_annotations "
        "WHERE trace_id = 't1' GROUP BY span_id": "span_annotations_span",
        "SELECT id, name FROM eval_annotations "
        "WHERE eval_id = 'e1' AND dataset_id = 'd'": "eval_annotations_eval",
    }
    with backend.pool.get_connection(db_path) as conn:
        for sql, index in viewer_lookups.items():
            plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
            assert f"INDEX {index}" in plan[0][3], (sql, plan)
