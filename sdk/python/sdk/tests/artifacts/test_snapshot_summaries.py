"""The summary tables an export adds to a snapshot hold what the viewer computes on
read from the same snapshot."""

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends._snapshot_summaries import SUMMARY_TABLES
from luml.experiments.backends.data_types import AnnotationKind, AnnotationValueType
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.backends.trace_schema import TRACE_EVAL_INDEXES
from luml.experiments.tracker import ExperimentTracker
from tests.artifacts.snapshot_helpers import connect_read_only, extract_snapshot_db
from tests.artifacts.summary_helpers import (
    VIEWER_TYPES,
    assert_summaries_match_reads,
    eval_column_types,
    exported_summary_tables,
    exports_key_catalogs,
    score_stats,
    span_attribute_types,
    stored_summaries,
    trace_summaries,
)
from tests.experiments.metric_helpers import (
    FIXTURES_DIR,
    LEGACY_INSERT,
    make_revision2_store,
)

EXP_ID = "exp"
SUMMARY_FIXTURES = [
    "i_gen2_sdk_0_6_0",
    "j_gen2_model_sdk_0_6_0",
    "k_gen2_from_rev2",
    "m_gen2_twin",
]
CONTENT_FIXTURES = [
    "i_gen2_sdk_0_6_0",
    "j_gen2_model_sdk_0_6_0",
    "k_gen2_from_rev2",
    "o_gen1_edge_sdk_0_5_0",
]


def _span(
    backend: SQLiteBackend,
    trace_id: str,
    span_id: str,
    start: int,
    end: int,
    parent: str | None = None,
    status: int | None = 1,
    attributes: dict[str, Any] | None = None,
) -> None:
    backend.log_span(
        EXP_ID,
        trace_id,
        span_id,
        f"span {span_id}",
        start,
        end,
        parent_span_id=parent,
        status_code=status,
        attributes=attributes,
    )


def _log_edge_traces(backend: SQLiteBackend) -> None:
    _span(backend, "ok", "root", 0, 100, attributes={"model": "a", "tokens": 3})
    _span(backend, "ok", "child", 10, 90, parent="root", status=2)
    _span(backend, "error", "root", 0, 100, status=2, attributes={"flag": True})
    _span(backend, "unset", "root", 5, 105, status=0, attributes={"flag": False})
    _span(backend, "no_status", "root", 5, 105, status=None)
    _span(backend, "orphans", "a", 0, 50, parent="missing")
    _span(backend, "orphans", "b", 20, 70, parent="missing", attributes={"x": None})
    # Re-logged with INSERT OR REPLACE: the later row is the one that counts.
    _span(backend, "relogged", "root", 0, 10)
    _span(backend, "relogged", "root", 0, 40, attributes={"model": "b"})
    _span(backend, "nan", "root", 0, 100, attributes={"loss": math.nan, "tag": "n"})


def _log_edge_evals(backend: SQLiteBackend) -> None:
    samples: list[tuple[str, str, dict[str, Any] | None]] = [
        ("a", "e1", {"acc": 1.0, "passed": True, "grade": "A", "none": None}),
        ("a", "e2", {"acc": 0.25, "passed": False, "nested": {"x": 1}}),
        ("a", "e3", {"acc": math.nan, "passed": True}),
        ("a", "e4", None),
        ("a", "e5", {"count": 3}),
        ("b", "e1", {"acc": 0.5}),
    ]
    for dataset_id, eval_id, scores in samples:
        backend.log_eval_sample(
            EXP_ID,
            eval_id,
            dataset_id,
            {"question": eval_id},
            outputs={"answer": "x"} if eval_id == "e1" else None,
            scores=scores,
            metadata={"loss": math.nan} if eval_id == "e5" else None,
        )
    backend.log_eval_annotation(
        EXP_ID,
        "a",
        "e2",
        "helpful",
        AnnotationKind.FEEDBACK,
        AnnotationValueType.BOOL,
        True,
        "user",
    )
    # Re-logged after it got an annotation; the later scores are the ones that count.
    backend.log_eval_sample(EXP_ID, "e2", "a", {"question": "e2"}, scores={"acc": 0.75})


def _write_raw_edge_rows(db_path: Path) -> None:
    """Values the SDK never writes but a reader must survive: scores that are not an
    object and text that is no JSON at all."""
    conn = sqlite3.connect(db_path)
    rows = [
        ("c", "array", '[1, true, "x"]'),
        ("c", "number", "5"),
        ("c", "string", '"text"'),
        ("c", "null", "null"),
        ("c", "garbage", "{not json"),
        ("c", "big", '{"huge": 1e400, "int": 9223372036854775807}'),
        ("c", "more_ints", '{"int": 9223372036854775807}'),
    ]
    conn.executemany(
        "INSERT INTO evals (id, dataset_id, inputs, scores) VALUES (?, ?, ?, ?)",
        [(eval_id, dataset, "{not json", scores) for dataset, eval_id, scores in rows],
    )
    conn.execute(
        "INSERT INTO spans (trace_id, span_id, name, start_time_unix_nano, "
        "end_time_unix_nano, attributes) VALUES ('raw', 's', 'n', 0, 1, '{oops')"
    )
    conn.execute(
        "INSERT INTO spans (trace_id, span_id, name, start_time_unix_nano, "
        "end_time_unix_nano, attributes) VALUES ('raw', 't', 'n', 0, 1, '[\"a\"]')"
    )
    conn.commit()
    conn.close()


def _edge_store(store: Path) -> SQLiteBackend:
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.initialize_experiment(EXP_ID, name=EXP_ID)
    _log_edge_traces(backend)
    _log_edge_evals(backend)
    backend.flush(EXP_ID)
    _write_raw_edge_rows(store / EXP_ID / "exp.db")
    return backend


def _snapshot_copy(backend: SQLiteBackend, dest: Path) -> Path:
    with backend.snapshot_experiment(EXP_ID) as snapshot:
        assert snapshot.artifact_generation == 2
        dest.write_bytes(snapshot.path.read_bytes())
    return dest


def _objects(conn: sqlite3.Connection, kind: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = ? "
            "AND name NOT LIKE 'sqlite_autoindex%'",
            (kind,),
        )
    }


def test_summaries_of_an_export_equal_reads_of_the_snapshot(tmp_path: Path) -> None:
    backend = _edge_store(tmp_path / "store")
    snapshot = _snapshot_copy(backend, tmp_path / "snapshot.db")
    backend.close()

    conn = connect_read_only(snapshot)
    try:
        assert_summaries_match_reads(conn, exports_key_catalogs())
        stored = stored_summaries(conn)
    finally:
        conn.close()
    traces = stored["traces"]
    assert {trace_id: row[4] for trace_id, row in traces.items()} == {
        "ok": 1,
        "error": 2,
        "unset": 0,
        "no_status": 3,
        "orphans": 3,
        "relogged": 1,
        "nan": 1,
        "raw": 3,
    }
    assert traces["relogged"][:4] == (0, 40, 40, 1)
    assert traces["orphans"][:4] == (0, 70, 70, 2)
    assert stored["scores"] == {
        ("a", "acc"): (2, 1.75),
        ("a", "passed"): (1, 1.0),
        ("a", "count"): (1, 3.0),
        ("b", "acc"): (1, 0.5),
        ("c", "0"): (1, 1.0),
        ("c", "1"): (1, 1.0),
        ("c", "huge"): (1, math.inf),
        ("c", "int"): (2, 2 * 9223372036854775807.0),
    }
    if not exports_key_catalogs():
        return
    assert stored["attributes"] == {
        "0": "text",
        "flag": stored["attributes"]["flag"],
        "loss": "null",
        "model": "text",
        "tag": "text",
        "tokens": "integer",
        "x": "null",
    }
    assert stored["attributes"]["flag"] in ("true", "false")
    assert stored["columns"][("a", "metadata", "loss")] == "null"
    assert ("a", "scores", "nested") not in stored["columns"]
    assert ("c", "inputs", "question") not in stored["columns"]


def test_summaries_and_indexes_are_built_in_the_copy_only(tmp_path: Path) -> None:
    store = tmp_path / "store"
    backend = _edge_store(store)
    live = store / EXP_ID / "exp.db"
    conn = connect_read_only(live)
    live_tables = _objects(conn, "table")
    conn.close()
    snapshot = _snapshot_copy(backend, tmp_path / "snapshot.db")
    backend.close()

    assert not live_tables & set(SUMMARY_TABLES)
    conn = connect_read_only(live)
    assert _objects(conn, "table") == live_tables
    conn.close()
    conn = connect_read_only(snapshot)
    try:
        tables = _objects(conn, "table")
        assert set(SUMMARY_TABLES) & tables == exported_summary_tables()
        assert set(TRACE_EVAL_INDEXES) <= _objects(conn, "index")
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    finally:
        conn.close()


def test_an_export_on_sqlite_before_3_45_omits_the_key_catalogs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = _edge_store(tmp_path / "store")
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 44, 2))
    snapshot = _snapshot_copy(backend, tmp_path / "snapshot.db")
    backend.close()

    conn = connect_read_only(snapshot)
    try:
        tables = _objects(conn, "table")
        assert set(SUMMARY_TABLES) & tables == {
            "snapshot_trace_summaries",
            "snapshot_eval_score_stats",
        }
        assert_summaries_match_reads(conn, key_catalogs=False)
        assert set(TRACE_EVAL_INDEXES) <= _objects(conn, "index")
    finally:
        conn.close()


def test_an_export_adds_indexes_a_revision_3_store_lacks(tmp_path: Path) -> None:
    store = tmp_path / "store"
    backend = _edge_store(store)
    conn = sqlite3.connect(store / EXP_ID / "exp.db")
    for name in TRACE_EVAL_INDEXES:
        conn.execute(f"DROP INDEX {name}")
    conn.commit()
    conn.close()
    snapshot = _snapshot_copy(backend, tmp_path / "snapshot.db")
    backend.close()

    conn = connect_read_only(snapshot)
    try:
        assert set(TRACE_EVAL_INDEXES) <= _objects(conn, "index")
        assert_summaries_match_reads(conn, exports_key_catalogs())
    finally:
        conn.close()


def test_a_revision_2_store_exports_with_indexes_and_summaries(tmp_path: Path) -> None:
    store = tmp_path / "store"
    db_path = make_revision2_store(store, EXP_ID)
    backend = SQLiteBackend(str(store), flush_interval=0)
    _log_edge_traces(backend)
    _log_edge_evals(backend)
    backend.flush(EXP_ID)

    conn = connect_read_only(db_path)
    assert conn.execute("PRAGMA user_version").fetchone() == (2,)
    assert not _objects(conn, "index")
    conn.close()
    snapshot = _snapshot_copy(backend, tmp_path / "snapshot.db")
    backend.close()

    conn = connect_read_only(snapshot)
    try:
        assert conn.execute("PRAGMA user_version").fetchone() == (3,)
        assert set(TRACE_EVAL_INDEXES) <= _objects(conn, "index")
        tables = _objects(conn, "table")
        assert set(SUMMARY_TABLES) & tables == exported_summary_tables()
        assert_summaries_match_reads(conn, exports_key_catalogs())
    finally:
        conn.close()


def test_the_generation_1_fallback_has_no_indexes_or_summaries(tmp_path: Path) -> None:
    store = tmp_path / "store"
    db_path = make_revision2_store(store, EXP_ID)
    conn = sqlite3.connect(db_path)
    conn.execute(LEGACY_INSERT, ("loss", 1.0, 2.5, None))
    conn.commit()
    conn.close()
    backend = SQLiteBackend(str(store), flush_interval=0)
    _log_edge_traces(backend)
    _log_edge_evals(backend)

    with backend.snapshot_experiment(EXP_ID) as snapshot:
        assert snapshot.artifact_generation == 1
        conn = connect_read_only(snapshot.path)
        try:
            assert not _objects(conn, "index")
            assert not set(SUMMARY_TABLES) & _objects(conn, "table")
        finally:
            conn.close()
    backend.close()
    tracker = ExperimentTracker(f"sqlite://{store}")
    reference = tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)
    assert reference.snapshot_member() == "exp.db.zip"


def _fixture_db(name: str, tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / f"{name}.db"
    extract_snapshot_db(FIXTURES_DIR / f"{name}.tar", db)
    return connect_read_only(db)


def _expected(name: str) -> dict[str, Any]:
    text = (FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8")
    return json.loads(text)["expected"]


@pytest.mark.parametrize("name", SUMMARY_FIXTURES)
def test_fixture_summaries_equal_reads_of_the_fixture(
    name: str, tmp_path: Path
) -> None:
    conn = _fixture_db(name, tmp_path)
    try:
        assert set(SUMMARY_TABLES) <= _objects(conn, "table")
        assert set(TRACE_EVAL_INDEXES) <= _objects(conn, "index")
        assert_summaries_match_reads(conn, key_catalogs=True)
    finally:
        conn.close()


@pytest.mark.parametrize("name", CONTENT_FIXTURES)
def test_fixture_reads_equal_the_vectors_of_its_description(
    name: str, tmp_path: Path
) -> None:
    """The vectors are computed from what was logged; the TypeScript reader tests the
    same ones, on revision 2 through the tables and on revision 3 through the
    summaries."""
    expected = _expected(name)
    conn = _fixture_db(name, tmp_path)
    try:
        summaries = trace_summaries(conn)
        assert {
            trace_id: (row[2], row[3], row[4]) for trace_id, row in summaries.items()
        } == {
            trace["trace_id"]: (
                trace["execution_time"],
                trace["span_count"],
                trace["state"],
            )
            for trace in expected["traces"]
        }
        stats = score_stats(conn)
        averages = {
            dataset_id: {
                key: total / count
                for (stats_dataset, key), (count, total) in stats.items()
                if stats_dataset == dataset_id
            }
            for dataset_id in expected["datasets"]
        }
        for dataset_id, dataset in expected["datasets"].items():
            assert averages[dataset_id].keys() == dataset["average_scores"].keys()
            for key, value in dataset["average_scores"].items():
                assert math.isclose(averages[dataset_id][key], value, rel_tol=1e-12)
        assert {
            key: _viewer_type(types)
            for key, types in sorted(span_attribute_types(conn).items())
        } == expected["span_attribute_keys"]
        columns = eval_column_types(conn)
        for dataset_id, dataset in expected["datasets"].items():
            for column, keys in dataset["column_keys"].items():
                assert {
                    key: _viewer_type(types)
                    for (d, c, key), types in sorted(columns.items())
                    if (d, c) == (dataset_id, column)
                } == keys, (dataset_id, column)
    finally:
        conn.close()


def _viewer_type(types: set[str]) -> str:
    (viewer_type,) = {VIEWER_TYPES.get(kind, "unknown") for kind in types}
    return viewer_type
