# flake8: noqa: E501
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends._exceptions import (
    ExperimentReaderTooOldError,
    ExperimentSchemaError,
    ExperimentWriterTooOldError,
    LegacyMetricRowsError,
    SQLiteVersionError,
)
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import (
    LEGACY_INSERT,
    assert_bucket_invariants,
    build_revision2_db,
    make_revision2_store,
    make_store,
    schema_snapshot,
)

EXPERIMENT_ID = "exp"
ROWS = [
    ("loss", 2.0, 0, "2026-01-02 03:04:05"),
    ("loss", 1.0, 1, "2026-01-02 03:04:06"),
    ("loss", None, 2, "2026-01-02 03:04:07"),
    ("loss", float("inf"), 3, "2026-01-02 03:04:08"),
    ("acc", 0.5, 10, "2026-01-02 03:04:09"),
    ("acc", 0.75, -3, "2026-01-02 03:04:10"),
]

# The metric statements of the released SDK (origin/main sqlite.py), verbatim.
RELEASED_READS: list[tuple[str, tuple[Any, ...]]] = [
    ("SELECT MAX(step) FROM dynamic_metrics WHERE key = ?", ("loss",)),
    ("SELECT MAX(step) FROM dynamic_metrics WHERE key = ?", ("missing",)),
    ("SELECT key, value, step FROM dynamic_metrics ORDER BY key, step", ()),
    ("SELECT DISTINCT key FROM dynamic_metrics", ()),
    (
        """
                SELECT key, value FROM dynamic_metrics dm1
                WHERE step = (SELECT MAX(step) FROM dynamic_metrics dm2 WHERE dm2.key = dm1.key)
                """,
        (),
    ),
    (
        "SELECT value, step, logged_at FROM dynamic_metrics WHERE key = ? ORDER BY step",
        ("loss",),
    ),
]
RELEASED_INSERT = """
                INSERT OR REPLACE INTO dynamic_metrics (key, value, step)
                VALUES (?, ?, ?)
            """


def _revision2_store(tmp_path: Path) -> tuple[Path, Path]:
    store = tmp_path / "store"
    db_path = make_revision2_store(store, EXPERIMENT_ID)
    conn = sqlite3.connect(db_path)
    conn.executemany(LEGACY_INSERT, ROWS)
    conn.commit()
    conn.close()
    return store, db_path


def _read_everything(backend: SQLiteBackend) -> None:
    experiment = backend.get_experiment(EXPERIMENT_ID)
    assert experiment is not None
    group_id = experiment.group_id
    assert group_id is not None
    reads: list[Callable[[], object]] = [
        lambda: backend.get_experiment_data(EXPERIMENT_ID),
        lambda: backend.get_experiment_metric_history(EXPERIMENT_ID, "loss"),
        lambda: backend.get_group_experiments_dynamic_metrics_keys(group_id),
        lambda: backend.get_group_experiments_static_params_keys(group_id),
        lambda: backend.resolve_experiment_sort_column(group_id, "loss"),
        lambda: backend.get_metric_catalog(EXPERIMENT_ID),
        lambda: backend.get_metric_buckets(EXPERIMENT_ID, "loss", 0),
        lambda: backend.get_metric_buckets(EXPERIMENT_ID, "loss", 5),
        lambda: backend.list_attachments(EXPERIMENT_ID),
        lambda: backend.list_attachments_tree(EXPERIMENT_ID),
        lambda: backend.get_experiment_traces(EXPERIMENT_ID),
        lambda: backend.get_experiment_traces_all(EXPERIMENT_ID),
        lambda: backend.get_trace(EXPERIMENT_ID, "none"),
        lambda: backend.get_experiment_evals(EXPERIMENT_ID),
        lambda: backend.get_experiment_evals_all(EXPERIMENT_ID),
        lambda: backend.get_eval(EXPERIMENT_ID, "none"),
        lambda: backend.get_experiment_eval_columns(EXPERIMENT_ID),
        lambda: backend.get_experiment_eval_typed_columns(EXPERIMENT_ID),
        lambda: backend.get_experiment_trace_columns(EXPERIMENT_ID),
        lambda: backend.get_experiment_trace_typed_columns(EXPERIMENT_ID),
        lambda: backend.get_experiment_eval_dataset_ids(EXPERIMENT_ID),
        lambda: backend.get_evals_average_scores(EXPERIMENT_ID),
        lambda: backend.get_eval_annotations(EXPERIMENT_ID, "ds", "none"),
        lambda: backend.get_span_annotations(EXPERIMENT_ID, "t", "s"),
        lambda: backend.get_all_traces_annotation_summary(EXPERIMENT_ID),
        lambda: backend.get_experiment_ddl_version(EXPERIMENT_ID),
        lambda: backend.export_experiment_db(EXPERIMENT_ID),
        lambda: backend.end_experiment(EXPERIMENT_ID),
    ]
    for read in reads:
        read()


def test_reads_never_migrate_a_revision_2_experiment(tmp_path: Path) -> None:
    store, db_path = _revision2_store(tmp_path)
    before = schema_snapshot(db_path)

    backend = SQLiteBackend(str(store))
    _read_everything(backend)
    assert schema_snapshot(db_path) == before
    assert backend.get_experiment_ddl_version(EXPERIMENT_ID) == 2

    backend.log_dynamic(EXPERIMENT_ID, "loss", 0.5)
    backend.flush()
    assert backend.get_experiment_ddl_version(EXPERIMENT_ID) == 3
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "loss")
    assert [point["step"] for point in history] == [0, 1, 2, 3, 4]
    backend.close()
    conn = sqlite3.connect(db_path)
    assert_bucket_invariants(conn)
    conn.close()


@pytest.mark.parametrize(
    "write",
    [
        lambda b: b.log_static(EXPERIMENT_ID, "lr", 0.1),
        lambda b: b.log_attachment(EXPERIMENT_ID, "a.txt", "x"),
        lambda b: b.log_eval_sample(EXPERIMENT_ID, "e1", "ds", {"q": 1}),
        lambda b: b.log_span(EXPERIMENT_ID, "t", "s", "n", 0, 1),
    ],
)
def test_any_write_migrates(
    tmp_path: Path, write: Callable[[SQLiteBackend], None]
) -> None:
    store, _ = _revision2_store(tmp_path)
    backend = SQLiteBackend(str(store))
    write(backend)
    backend.flush()
    assert backend.get_experiment_ddl_version(EXPERIMENT_ID) == 3
    backend.close()


def _released_reads(db_path: Path) -> list[list[tuple[Any, ...]]]:
    conn = sqlite3.connect(db_path)
    try:
        return [
            sorted(conn.execute(sql, params).fetchall(), key=repr)
            for sql, params in RELEASED_READS
        ]
    finally:
        conn.close()


def test_released_sdk_statements_on_revision_3(tmp_path: Path) -> None:
    store, db_path = _revision2_store(tmp_path)
    on_revision_2 = _released_reads(db_path)

    backend = SQLiteBackend(str(store))
    backend.log_static(EXPERIMENT_ID, "migrate", 1)
    backend.close()
    assert schema_snapshot(db_path)[1] == 3
    assert _released_reads(db_path) == on_revision_2

    conn = sqlite3.connect(db_path)
    points_before = conn.execute("SELECT * FROM metric_points").fetchall()
    with pytest.raises(
        sqlite3.IntegrityError, match="schema revision 3; upgrade luml-sdk"
    ):
        conn.execute(RELEASED_INSERT, ("loss", 1.0, 99))
    conn.rollback()
    assert conn.execute("SELECT * FROM metric_points").fetchall() == points_before
    assert_bucket_invariants(conn)
    conn.close()
    assert _released_reads(db_path) == on_revision_2


def _set_revision_4(db_path: Path, min_reader: int, min_writer: int) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exp_schema_migrations (version) VALUES (4)")
    conn.execute(
        "UPDATE exp_schema_info SET value = ? WHERE key = 'min_reader_revision'",
        (str(min_reader),),
    )
    conn.execute(
        "UPDATE exp_schema_info SET value = ? WHERE key = 'min_writer_revision'",
        (str(min_writer),),
    )
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()


def _revision4_store(
    tmp_path: Path, min_reader: int, min_writer: int
) -> tuple[Path, Path]:
    store = tmp_path / "store"
    make_store(store, EXPERIMENT_ID)
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.log_dynamic(EXPERIMENT_ID, "loss", 1.0)
    backend.close()
    db_path = store / EXPERIMENT_ID / "exp.db"
    _set_revision_4(db_path, min_reader, min_writer)
    return store, db_path


def test_revision_4_needing_a_newer_reader_is_refused(tmp_path: Path) -> None:
    store, db_path = _revision4_store(tmp_path, min_reader=4, min_writer=4)
    before = schema_snapshot(db_path)
    backend = SQLiteBackend(str(store))
    with pytest.raises(ExperimentReaderTooOldError, match="needs a newer reader"):
        backend.get_experiment_data(EXPERIMENT_ID)
    with pytest.raises(ExperimentReaderTooOldError):
        backend.get_metric_catalog(EXPERIMENT_ID)
    with pytest.raises(ExperimentReaderTooOldError):
        backend.get_experiment_evals(EXPERIMENT_ID)
    with pytest.raises(ExperimentSchemaError):
        backend.log_dynamic(EXPERIMENT_ID, "loss", 2.0)
    with pytest.raises(ExperimentSchemaError):
        backend.log_static(EXPERIMENT_ID, "lr", 0.1)
    assert backend._write_buffer._rows == {}
    backend.close()
    assert schema_snapshot(db_path) == before


def test_revision_4_readable_and_writable_is_used_without_migrating(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, db_path = _revision4_store(tmp_path, min_reader=2, min_writer=3)
    before = schema_snapshot(db_path)
    backend = SQLiteBackend(str(store))
    with caplog.at_level(logging.WARNING):
        backend.log_dynamic(EXPERIMENT_ID, "loss", 2.0)
        backend.log_static(EXPERIMENT_ID, "lr", 0.1)
        history = backend.get_experiment_metric_history(EXPERIMENT_ID, "loss")
        backend.get_metric_catalog(EXPERIMENT_ID)
    assert [point["value"] for point in history] == [1.0, 2.0]
    warnings = [r for r in caplog.records if "newer than" in r.getMessage()]
    assert len(warnings) == 1
    backend.close()
    assert schema_snapshot(db_path) == before
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT MAX(version) FROM exp_schema_migrations"
    ).fetchone() == (4,)
    assert_bucket_invariants(conn)
    conn.close()


def test_revision_4_needing_a_newer_writer_reads_but_refuses_writes(
    tmp_path: Path,
) -> None:
    store, db_path = _revision4_store(tmp_path, min_reader=2, min_writer=4)
    before = schema_snapshot(db_path)
    backend = SQLiteBackend(str(store))
    assert backend.get_experiment_data(EXPERIMENT_ID).dynamic_metrics == {
        "loss": [{"value": 1.0, "step": 0}]
    }
    writes: list[Callable[[], object]] = [
        lambda: backend.log_dynamic(EXPERIMENT_ID, "loss", 2.0),
        lambda: backend.log_static(EXPERIMENT_ID, "lr", 0.1),
        lambda: backend.log_span(EXPERIMENT_ID, "t", "s", "n", 0, 1),
        lambda: backend.log_eval_sample(EXPERIMENT_ID, "e1", "ds", {"q": 1}),
        lambda: backend.log_attachment(EXPERIMENT_ID, "a.txt", "x"),
    ]
    for write in writes:
        with pytest.raises(ExperimentWriterTooOldError, match="needs a newer writer"):
            write()
        assert backend._write_buffer._rows == {}
    backend.close()
    assert schema_snapshot(db_path) == before


def test_a_database_past_every_known_revision_gets_no_missing_migration(
    tmp_path: Path,
) -> None:
    db_path = build_revision2_db(tmp_path / "exp.db")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exp_schema_migrations (version) VALUES (4)")
    conn.commit()
    before = schema_snapshot(db_path)

    assert ExperimentMigrationRunner(conn).migrate() == []
    conn.close()
    assert schema_snapshot(db_path) == before


def _revision2_store_with(tmp_path: Path, rows: list[tuple[Any, ...]]) -> Path:
    store, db_path = _revision2_store(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.executemany(LEGACY_INSERT, rows)
    conn.commit()
    conn.close()
    return store


def test_unmigratable_rows_refuse_writes_at_the_call_and_keep_reads_working(
    tmp_path: Path,
) -> None:
    store = _revision2_store_with(tmp_path, [("loss", 7.0, 2.5, None)])
    db_path = store / EXPERIMENT_ID / "exp.db"
    before = schema_snapshot(db_path)
    backend = SQLiteBackend(str(store), flush_interval=3600)
    writes: list[Callable[[], object]] = [
        lambda: backend.log_dynamic(EXPERIMENT_ID, "loss", 9.0),
        lambda: backend.log_dynamic(EXPERIMENT_ID, "acc", 9.0, step=1),
        lambda: backend.log_span(EXPERIMENT_ID, "t", "s", "n", 0, 1),
        lambda: backend.log_eval_sample(EXPERIMENT_ID, "e1", "ds", {"q": 1}),
        lambda: backend.log_static(EXPERIMENT_ID, "lr", 0.1),
    ]
    for write in writes:
        with pytest.raises(LegacyMetricRowsError, match="key 'loss', step 2.5"):
            write()
        assert backend._write_buffer._rows == {}

    catalog = backend.get_metric_catalog(EXPERIMENT_ID)
    assert (catalog.revision, catalog.skipped_rows) == (2, 0)
    assert [(m.key, m.last_step, m.count) for m in catalog.metrics] == [
        ("acc", 10, None),
        ("loss", 3, None),
    ]
    buckets = backend.get_metric_buckets(EXPERIMENT_ID, "loss", 0)
    assert [(b.bucket, b.count) for b in buckets.buckets] == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
    ]
    buckets = backend.get_metric_buckets(EXPERIMENT_ID, "loss", 1)
    assert [(b.bucket, b.count, b.sum) for b in buckets.buckets] == [(0, 4, 3.0)]
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "loss")
    assert [point["step"] for point in history] == [0, 1, 2, 2.5, 3]
    _read_everything(backend)
    backend.flush()
    backend.close()
    assert schema_snapshot(db_path) == before


def test_revision_2_bucket_span_ignores_real_steps_at_both_ends(
    tmp_path: Path,
) -> None:
    store = _revision2_store_with(
        tmp_path, [("loss", 7.0, -2.5, None), ("loss", 8.0, 7.5, None)]
    )
    backend = SQLiteBackend(str(store), flush_interval=3600)

    buckets = backend.get_metric_buckets(EXPERIMENT_ID, "loss", 0)

    assert (buckets.first_step, buckets.last_step) == (0, 3)
    assert [b.bucket for b in buckets.buckets] == [0, 1, 2, 3]
    backend.close()


def test_numpy_steps_are_skipped_by_revision_2_reads_and_decoded_on_write(
    tmp_path: Path,
) -> None:
    numpy_rows = [
        ("np", float(step), step.to_bytes(8, "little", signed=True), None)
        for step in (5, 6, 7)
    ]
    store = _revision2_store_with(tmp_path, numpy_rows)
    backend = SQLiteBackend(str(store), flush_interval=0)
    catalog = backend.get_metric_catalog(EXPERIMENT_ID)
    assert catalog.skipped_rows == 3
    assert "np" not in [m.key for m in catalog.metrics]
    assert backend.get_metric_buckets(EXPERIMENT_ID, "np", 0).buckets == []

    backend.log_dynamic(EXPERIMENT_ID, "np", 8.0)
    catalog = backend.get_metric_catalog(EXPERIMENT_ID)
    assert catalog.skipped_rows == 0
    assert ("np", 5, 8, 4) in [
        (m.key, m.first_step, m.last_step, m.count) for m in catalog.metrics
    ]
    backend.close()
    conn = sqlite3.connect(store / EXPERIMENT_ID / "exp.db")
    assert_bucket_invariants(conn)
    conn.close()


def test_a_non_integer_stored_step_fails_the_implicit_step_call(
    tmp_path: Path,
) -> None:
    store = tmp_path / "store"
    make_store(store, EXPERIMENT_ID)
    backend = SQLiteBackend(str(store), flush_interval=3600)
    backend.log_dynamic(EXPERIMENT_ID, "acc", 1.0, step=0)
    backend.flush()
    conn = sqlite3.connect(store / EXPERIMENT_ID / "exp.db")
    conn.execute(
        "INSERT INTO metric_points (metric_id, step, value) "
        "SELECT id, 3.5, 1.0 FROM metric_keys"
    )
    conn.commit()
    conn.close()

    backend.log_span(EXPERIMENT_ID, "t", "s", "n", 0, 1)
    with pytest.raises(TypeError, match="integer"):
        backend.log_dynamic(EXPERIMENT_ID, "acc", 2.0)
    backend.log_dynamic(EXPERIMENT_ID, "acc", 2.0, step=1)
    backend.flush()
    assert backend._write_buffer._rows == {}
    assert len(backend.get_experiment_traces_all(EXPERIMENT_ID)) == 1
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "acc")
    assert [point["step"] for point in history] == [0, 1, 3.5]
    backend.close()


def test_backend_refuses_sqlite_without_generated_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 30, 1))
    monkeypatch.setattr(sqlite3, "sqlite_version", "3.30.1")
    with pytest.raises(SQLiteVersionError, match="SQLite 3.31.0 or newer"):
        SQLiteBackend(str(tmp_path / "store"))
    assert not (tmp_path / "store").exists()


def test_new_and_migrated_databases_have_the_same_schema(tmp_path: Path) -> None:
    new_store, migrated_store = tmp_path / "new", tmp_path / "migrated"
    make_store(new_store, EXPERIMENT_ID)
    migrated_db = make_revision2_store(migrated_store, EXPERIMENT_ID)
    backend = SQLiteBackend(str(migrated_store), flush_interval=0)
    backend.log_static(EXPERIMENT_ID, "migrate", 1)
    backend.close()

    new_schema = schema_snapshot(new_store / EXPERIMENT_ID / "exp.db")
    assert schema_snapshot(migrated_db) == new_schema
    conn = sqlite3.connect(migrated_db, detect_types=sqlite3.PARSE_DECLTYPES)
    declared = conn.execute(
        "SELECT name, type, hidden FROM pragma_table_xinfo('metric_points')"
    ).fetchall()
    conn.close()
    assert ("logged_at", "TIMESTAMP", 2) in declared
