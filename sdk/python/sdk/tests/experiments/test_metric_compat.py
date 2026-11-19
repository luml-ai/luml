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
from luml.experiments.backends.data_types import AnnotationKind, AnnotationValueType
from luml.experiments.backends.metric_store import METRIC_POINT_SQL
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
    assert backend.get_experiment_ddl_version(EXPERIMENT_ID) == 4
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "loss")
    assert [point["step"] for point in history] == [0, 1, 2, 3, 4]
    backend.close()
    conn = sqlite3.connect(db_path)
    assert_bucket_invariants(conn)
    conn.close()


def _write_everything_but_metrics_once(backend: SQLiteBackend) -> None:
    backend.log_static(EXPERIMENT_ID, "lr", 0.1)
    backend.log_attachment(EXPERIMENT_ID, "a.txt", "x")
    backend.log_eval_sample(EXPERIMENT_ID, "e1", "ds", {"q": 1})
    backend.log_span(EXPERIMENT_ID, "t", "s", "n", 0, 1)
    backend.flush()
    backend.link_eval_sample_to_trace(EXPERIMENT_ID, "ds", "e1", "t")
    annotation = backend.log_eval_annotation(
        EXPERIMENT_ID,
        "ds",
        "e1",
        "good",
        AnnotationKind.FEEDBACK,
        AnnotationValueType.BOOL,
        True,
        "u",
    )
    backend.update_annotation(EXPERIMENT_ID, annotation.id, "eval", value=False)
    backend.log_span_annotation(
        EXPERIMENT_ID,
        "t",
        "s",
        "note",
        AnnotationKind.FEEDBACK,
        AnnotationValueType.BOOL,
        True,
        "u",
    )
    backend.delete_annotation(EXPERIMENT_ID, annotation.id, "eval")
    backend.flush()


def test_only_a_metric_write_migrates(tmp_path: Path) -> None:
    store, db_path = _revision2_store(tmp_path)
    before = schema_snapshot(db_path)
    backend = SQLiteBackend(str(store))

    _write_everything_but_metrics_once(backend)
    assert schema_snapshot(db_path) == before
    assert backend.get_experiment_ddl_version(EXPERIMENT_ID) == 2
    # A released SDK still logging to this store keeps working.
    conn = sqlite3.connect(db_path)
    conn.execute(RELEASED_INSERT, ("loss", 1.0, 99))
    conn.commit()
    conn.close()

    backend.log_dynamic(EXPERIMENT_ID, "loss", 0.5)
    backend.flush()
    assert backend.get_experiment_ddl_version(EXPERIMENT_ID) == 4
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "loss")
    assert [point["step"] for point in history] == [0, 1, 2, 3, 99, 100]
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


def test_released_sdk_statements_on_revision_4(tmp_path: Path) -> None:
    store, db_path = _revision2_store(tmp_path)
    on_revision_2 = _released_reads(db_path)

    conn = sqlite3.connect(db_path)
    assert ExperimentMigrationRunner(conn).migrate() == [3, 4]
    conn.close()
    assert schema_snapshot(db_path)[1] == 4
    assert _released_reads(db_path) == on_revision_2

    conn = sqlite3.connect(db_path)
    points_before = conn.execute("SELECT * FROM metric_points").fetchall()
    with pytest.raises(
        sqlite3.IntegrityError, match="schema revision 4; upgrade luml-sdk"
    ):
        conn.execute(RELEASED_INSERT, ("loss", 1.0, 99))
    conn.rollback()
    assert conn.execute("SELECT * FROM metric_points").fetchall() == points_before
    assert_bucket_invariants(conn)
    conn.close()
    assert _released_reads(db_path) == on_revision_2


def _set_revision_5(db_path: Path, min_reader: int, min_writer: int) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exp_schema_migrations (version) VALUES (5)")
    conn.execute(
        "UPDATE exp_schema_info SET value = ? WHERE key = 'min_reader_revision'",
        (str(min_reader),),
    )
    conn.execute(
        "UPDATE exp_schema_info SET value = ? WHERE key = 'min_writer_revision'",
        (str(min_writer),),
    )
    conn.execute("PRAGMA user_version = 5")
    conn.commit()
    conn.close()


def _revision5_store(
    tmp_path: Path, min_reader: int, min_writer: int
) -> tuple[Path, Path]:
    store = tmp_path / "store"
    make_store(store, EXPERIMENT_ID)
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.log_dynamic(EXPERIMENT_ID, "loss", 1.0)
    backend.close()
    db_path = store / EXPERIMENT_ID / "exp.db"
    _set_revision_5(db_path, min_reader, min_writer)
    return store, db_path


def test_revision_5_needing_a_newer_reader_is_refused(tmp_path: Path) -> None:
    store, db_path = _revision5_store(tmp_path, min_reader=5, min_writer=5)
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


def test_revision_5_readable_and_writable_is_used_without_migrating(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store, db_path = _revision5_store(tmp_path, min_reader=2, min_writer=4)
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
    ).fetchone() == (5,)
    assert_bucket_invariants(conn)
    conn.close()


def test_revision_5_needing_a_newer_writer_reads_but_refuses_writes(
    tmp_path: Path,
) -> None:
    store, db_path = _revision5_store(tmp_path, min_reader=2, min_writer=5)
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


def test_a_long_lived_reader_follows_a_migration_by_another_backend(
    tmp_path: Path,
) -> None:
    store, db_path = _revision2_store(tmp_path)
    reader = SQLiteBackend(str(store))
    catalog = reader.get_metric_catalog(EXPERIMENT_ID)
    assert (catalog.revision, catalog.bucket_max_level) == (2, None)

    writer = SQLiteBackend(str(store), flush_interval=0)
    writer.log_dynamic(EXPERIMENT_ID, "loss", 0.5)
    writer.close()

    catalog = reader.get_metric_catalog(EXPERIMENT_ID)
    assert catalog.revision == 4
    assert catalog.bucket_max_level is not None
    assert [(m.key, m.count) for m in catalog.metrics] == [("acc", 2), ("loss", 5)]
    assert reader.get_experiment_data(EXPERIMENT_ID).dynamic_metrics["loss"][-1] == {
        "value": 0.5,
        "step": 4,
    }

    _set_revision_5(db_path, min_reader=5, min_writer=5)
    with pytest.raises(ExperimentReaderTooOldError):
        reader.get_metric_catalog(EXPERIMENT_ID)
    reader.close()


def test_a_database_past_every_known_revision_gets_no_missing_migration(
    tmp_path: Path,
) -> None:
    db_path = build_revision2_db(tmp_path / "exp.db")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO exp_schema_migrations (version) VALUES (5)")
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


def _metric_rows(db_path: Path) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT key, value, step, logged_at FROM dynamic_metrics ORDER BY key, step"
        ).fetchall()
    finally:
        conn.close()


def _write_everything_but_metrics(backend: SQLiteBackend) -> None:
    backend.log_static(EXPERIMENT_ID, "lr", 0.1)
    backend.log_attachment(EXPERIMENT_ID, "notes.txt", "hello")
    backend.log_span(EXPERIMENT_ID, "t", "s", "n", 0, 1)
    backend.log_eval_sample(EXPERIMENT_ID, "e1", "ds", {"q": 1})


def _assert_metric_writes_refused(backend: SQLiteBackend) -> None:
    metric_writes: list[Callable[[], object]] = [
        lambda: backend.log_dynamic(EXPERIMENT_ID, "loss", 9.0),
        lambda: backend.log_dynamic(EXPERIMENT_ID, "acc", 9.0, step=1),
    ]
    for write in metric_writes:
        with pytest.raises(
            LegacyMetricRowsError, match="key 'loss', step 2.5"
        ) as raised:
            write()
        assert raised.value.count == 1
        buffered = [
            row for rows in backend._write_buffer._rows.values() for row in rows
        ]
        assert all(sql != METRIC_POINT_SQL for sql, _ in buffered)


def _assert_non_metric_writes_persisted(backend: SQLiteBackend) -> None:
    data = backend.get_experiment_data(EXPERIMENT_ID)
    assert data.static_params["lr"] == 0.1
    assert backend.get_attachment(EXPERIMENT_ID, "notes.txt") == b"hello"
    assert backend.get_trace(EXPERIMENT_ID, "t") is not None
    assert backend.get_eval(EXPERIMENT_ID, "e1") is not None


def test_unmigratable_rows_refuse_only_metric_writes_and_keep_reads_working(
    tmp_path: Path,
) -> None:
    store = _revision2_store_with(tmp_path, [("loss", 7.0, 2.5, None)])
    db_path = store / EXPERIMENT_ID / "exp.db"
    before = schema_snapshot(db_path)
    metric_rows = _metric_rows(db_path)
    backend = SQLiteBackend(str(store), flush_interval=3600)

    _assert_metric_writes_refused(backend)
    _write_everything_but_metrics(backend)
    _assert_metric_writes_refused(backend)
    backend.flush()
    _assert_non_metric_writes_persisted(backend)

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
    assert _metric_rows(db_path) == metric_rows

    later = SQLiteBackend(str(store), flush_interval=0)
    _assert_non_metric_writes_persisted(later)
    _assert_metric_writes_refused(later)
    later.log_static(EXPERIMENT_ID, "epochs", 3)
    assert later.get_experiment_data(EXPERIMENT_ID).static_params["epochs"] == 3
    with later.snapshot_experiment(EXPERIMENT_ID) as snapshot:
        assert snapshot.schema_revision == 2
        assert snapshot.fallback_reason is not None
        assert "key 'loss', step 2.5" in snapshot.fallback_reason
    later.close()
    assert schema_snapshot(db_path) == before
    assert _metric_rows(db_path) == metric_rows


def test_unmigratable_rows_still_get_the_earlier_migrations(tmp_path: Path) -> None:
    store = tmp_path / "store"
    make_store(store, EXPERIMENT_ID)
    db_path = store / EXPERIMENT_ID / "exp.db"
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate(target_version=1)
    conn.execute(LEGACY_INSERT, ("loss", 7.0, 2.5, None))
    conn.commit()
    conn.close()
    backend = SQLiteBackend(str(store), flush_interval=0)

    backend.log_attachment(EXPERIMENT_ID, "notes.txt", "hello")

    attachments = backend.list_attachments(EXPERIMENT_ID)
    assert [(a.name, a.size) for a in attachments] == [("notes.txt", 5)]
    with pytest.raises(LegacyMetricRowsError):
        backend.log_dynamic(EXPERIMENT_ID, "loss", 9.0)
    backend.close()
    conn = sqlite3.connect(db_path)
    versions = conn.execute(
        "SELECT version FROM exp_schema_migrations ORDER BY version"
    ).fetchall()
    conn.close()
    assert versions == [(1,), (2,)]
    assert _metric_rows(db_path) == [("loss", 7.0, 2.5, None)]


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


FRACTIONAL_ROWS = [
    ("loss", 7.0, -2.5, None),
    ("loss", 8.0, 1.5, None),
    ("loss", 9.0, 7.5, None),
]


@pytest.mark.parametrize("level", [0, 1, 5])
@pytest.mark.parametrize(
    ("key", "start_step", "end_step", "skipped"),
    [
        ("loss", None, None, 3),
        ("loss", 0, 3, 1),
        ("loss", -5, 0, 1),
        ("loss", None, 1, 1),
        ("loss", None, 2, 2),
        ("loss", 2, None, 1),
        ("loss", 2, 3, 0),
        ("acc", None, None, 0),
        ("acc", -3, 10, 0),
    ],
)
def test_revision_2_buckets_count_fractional_steps_and_keep_the_aggregates(
    tmp_path: Path,
    level: int,
    key: str,
    start_step: int | None,
    end_step: int | None,
    skipped: int,
) -> None:
    baseline = SQLiteBackend(str(_revision2_store(tmp_path / "baseline")[0]))
    fractional = SQLiteBackend(
        str(_revision2_store_with(tmp_path / "fractional", FRACTIONAL_ROWS))
    )

    expected = baseline.get_metric_buckets(
        EXPERIMENT_ID, key, level, start_step, end_step
    )
    result = fractional.get_metric_buckets(
        EXPERIMENT_ID, key, level, start_step, end_step
    )

    assert result.skipped_rows == skipped
    assert result.buckets == expected.buckets
    assert (result.first_step, result.last_step) == (
        expected.first_step,
        expected.last_step,
    )
    assert expected.skipped_rows == 0
    baseline.close()
    fractional.close()


@pytest.mark.parametrize("level", [0, 5, 20])
def test_revision_3_buckets_never_skip_rows(tmp_path: Path, level: int) -> None:
    store = tmp_path / "store"
    make_store(store, EXPERIMENT_ID)
    backend = SQLiteBackend(str(store), flush_interval=0)
    for step in range(10):
        backend.log_dynamic(EXPERIMENT_ID, "loss", float(step), step=step)

    result = backend.get_metric_buckets(EXPERIMENT_ID, "loss", level)

    assert result.buckets
    assert result.skipped_rows == 0
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


def _released_numpy_row(tmp_path: Path, dtype: str, step: int) -> Path:
    """A revision 2 store with the row SDK 0.5 stored for a numpy step: the
    scalar's raw bytes, except float64, which sqlite3 binds as a float."""
    np = pytest.importorskip("numpy")
    store, db_path = _revision2_store(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(RELEASED_INSERT, ("np", 1.0, getattr(np, dtype)(step)))
    conn.commit()
    conn.close()
    return store


@pytest.mark.parametrize(
    ("dtype", "step"),
    [
        ("int64", 3),
        ("int64", -3),
        ("int64", 2**40),
        ("int32", 3),
        ("int32", 2**29 - 1),
        ("uint32", 3),
        ("int16", 5),
        ("uint16", 2**10 - 1),
        ("int8", 7),
        ("uint8", 2**7 - 1),
    ],
)
def test_migration_decodes_a_numpy_step_that_can_only_be_an_integer(
    tmp_path: Path, dtype: str, step: int
) -> None:
    store = _released_numpy_row(tmp_path, dtype, step)
    backend = SQLiteBackend(str(store), flush_interval=0)
    backend.log_dynamic(EXPERIMENT_ID, "other", 1.0, step=1)
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "np")
    assert backend.get_metric_catalog(EXPERIMENT_ID).revision == 4
    backend.close()
    assert [point["step"] for point in history] == [step]


@pytest.mark.parametrize(
    ("dtype", "step"),
    [
        ("float32", 1),
        ("uint32", 4_000_000_000),
        ("int32", -1),
        ("int32", 2**29),
        ("float16", 1),
        ("uint16", 2**10),
        ("int8", -1),
        ("uint8", 2**7),
    ],
)
def test_a_numpy_step_that_may_not_be_an_integer_refuses_the_migration(
    tmp_path: Path, dtype: str, step: int
) -> None:
    store = _released_numpy_row(tmp_path, dtype, step)
    db_path = store / EXPERIMENT_ID / "exp.db"
    before = schema_snapshot(db_path)
    metric_rows = _metric_rows(db_path)
    backend = SQLiteBackend(str(store), flush_interval=0)

    with pytest.raises(LegacyMetricRowsError, match="key 'np', step X'") as raised:
        backend.log_dynamic(EXPERIMENT_ID, "loss", 9.0)
    assert raised.value.count == 1
    catalog = backend.get_metric_catalog(EXPERIMENT_ID)
    assert (catalog.revision, catalog.skipped_rows) == (2, 1)
    history = backend.get_experiment_metric_history(EXPERIMENT_ID, "loss")
    assert [point["step"] for point in history] == [0, 1, 2, 3]
    backend.close()
    assert schema_snapshot(db_path) == before
    assert _metric_rows(db_path) == metric_rows


@pytest.mark.parametrize(
    ("key", "value", "step"),
    [
        ("loss", 1.0, 1.5),
        ("loss", 1.0, "x"),
        ("loss", 1.0, 2**63),
        (object(), 1.0, 1),
        ("loss", object(), 1),
        ("loss", "high", 1),
    ],
    ids=["fractional", "text", "too-large", "key", "value", "text-value"],
)
def test_a_refused_metric_write_leaves_revision_2_to_released_writers(
    tmp_path: Path,
    key: Any,  # noqa: ANN401
    value: Any,  # noqa: ANN401
    step: Any,  # noqa: ANN401
) -> None:
    store, db_path = _revision2_store(tmp_path)
    before = schema_snapshot(db_path)
    backend = SQLiteBackend(str(store), flush_interval=0)

    with pytest.raises((TypeError, ValueError, OverflowError)):
        backend.log_dynamic(EXPERIMENT_ID, key, value, step=step)
    backend.close()

    assert schema_snapshot(db_path) == before
    conn = sqlite3.connect(db_path)
    versions = conn.execute("SELECT version FROM exp_schema_migrations").fetchall()
    conn.execute(RELEASED_INSERT, ("loss", 1.0, 7))
    conn.commit()
    conn.close()
    assert versions == [(1,), (2,)]


def test_a_non_integer_stored_step_drops_only_the_implicit_step_point(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
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
    backend.log_dynamic(EXPERIMENT_ID, "acc", 2.0)
    backend.log_dynamic(EXPERIMENT_ID, "acc", 2.0, step=1)
    backend.flush()
    assert "no integer step after 3.5" in caplog.text
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
    backend.log_dynamic(EXPERIMENT_ID, "migrate", 1.0)
    backend.close()

    new_schema = schema_snapshot(new_store / EXPERIMENT_ID / "exp.db")
    assert schema_snapshot(migrated_db) == new_schema
    conn = sqlite3.connect(migrated_db, detect_types=sqlite3.PARSE_DECLTYPES)
    declared = conn.execute(
        "SELECT name, type, hidden FROM pragma_table_xinfo('metric_points')"
    ).fetchall()
    conn.close()
    assert ("logged_at", "TIMESTAMP", 2) in declared
