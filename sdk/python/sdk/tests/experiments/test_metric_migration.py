import multiprocessing
import sqlite3
import threading
from pathlib import Path
from typing import Any

import pytest

from luml.experiments.backends._exceptions import LegacyMetricRowsError
from luml.experiments.backends.migration_runner import (
    KNOWN_EXPERIMENT_REVISION,
    ExperimentMigrationRunner,
    read_experiment_schema,
)
from luml.experiments.backends.sqlite import SQLiteBackend
from tests.experiments.metric_helpers import (
    LEGACY_INSERT,
    assert_bucket_invariants,
    assert_same_buckets,
    assert_same_catalog,
    build_revision2_db,
    extract_fixture_db,
    make_store,
    replace_experiment_db,
    same_value,
    schema_snapshot,
)

WRITABLE_FIXTURES = [
    "c_sdk_0_1_0",
    "d_sdk_0_5_0",
    "e_baseline_quirk",
    "f_model_sdk_0_5_0",
]
# Written before luml-sdk 0.1.0: only reading them has to keep working.
PRE_RELEASE_FIXTURES = [
    "a_premigration_legacy_indexes",
    "a_premigration_wal_lost",
    "b_premigration",
]
EXPERIMENT_ID = "fixture"
LEGACY_ROWS = (
    "SELECT key, value, step, logged_at FROM dynamic_metrics ORDER BY key, step"
)


def _legacy_rows(db_path: Path) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(LEGACY_ROWS).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _assert_same_rows(
    left: list[tuple[Any, ...]], right: list[tuple[Any, ...]]
) -> None:
    assert len(left) == len(right)
    for a, b in zip(left, right, strict=True):
        assert len(a) == len(b)
        for x, y in zip(a, b, strict=True):
            assert same_value(x, y), (a, b)


def _metric_reads(store: Path) -> dict[str, Any]:
    """Everything the backend's read methods return about the metrics."""
    backend = SQLiteBackend(str(store), flush_interval=0)
    try:
        data = backend.get_experiment_data(EXPERIMENT_ID)
        keys = sorted(data.dynamic_metrics)
        group_id = data.metadata.group_id
        buckets = {
            (key, level): backend.get_metric_buckets(EXPERIMENT_ID, key, level)
            for key in keys
            for level in range(15)
        }
        return {
            "data": data.dynamic_metrics,
            "static": data.static_params,
            "history": {
                key: backend.get_experiment_metric_history(EXPERIMENT_ID, key)
                for key in keys
            },
            "keys": backend.get_group_experiments_dynamic_metrics_keys(group_id),
            "catalog": backend.get_metric_catalog(EXPERIMENT_ID),
            "buckets": buckets,
        }
    finally:
        backend.close()


def _latest_values(store: Path) -> dict[str, Any]:
    backend = SQLiteBackend(str(store), flush_interval=0)
    try:
        backend.end_experiment(EXPERIMENT_ID)
        experiment = backend.get_experiment(EXPERIMENT_ID)
        assert experiment is not None
        return experiment.dynamic_params
    finally:
        backend.close()


def _assert_same_reads(before: dict[str, Any], after: dict[str, Any]) -> None:
    for name in ("data", "static", "history", "keys"):
        assert after[name] == before[name], name
    assert_same_catalog(before["catalog"], after["catalog"])
    assert after["buckets"].keys() == before["buckets"].keys()
    for request, result in before["buckets"].items():
        assert_same_buckets(result, after["buckets"][request])


def _fixture_store(tmp_path: Path, fixture: str) -> tuple[Path, Path]:
    store = tmp_path / "store"
    make_store(store, EXPERIMENT_ID)
    source = extract_fixture_db(fixture, tmp_path / "source" / "exp.db")
    return store, replace_experiment_db(store, EXPERIMENT_ID, source)


@pytest.mark.parametrize("fixture", WRITABLE_FIXTURES)
def test_migration_keeps_every_metric_row_and_read(
    tmp_path: Path, fixture: str
) -> None:
    store, db_path = _fixture_store(tmp_path, fixture)
    rows_before = _legacy_rows(db_path)
    assert rows_before, "fixture has metric rows"
    reads_before = _metric_reads(store)
    latest_before = _latest_values(store)
    assert read_experiment_schema(sqlite3.connect(db_path)).revision == 2

    conn = sqlite3.connect(db_path)
    try:
        assert ExperimentMigrationRunner(conn).migrate() == [3, 4]
        _assert_same_rows(rows_before, conn.execute(LEGACY_ROWS).fetchall())
        assert_bucket_invariants(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
        assert dict(conn.execute("SELECT key, value FROM exp_schema_info")) == {
            "min_reader_revision": "2",
            "min_writer_revision": "4",
            "bucket_min_level": "3",
            "bucket_max_level": "12",
        }
        assert ExperimentMigrationRunner(conn).migrate() == []
    finally:
        conn.close()

    _assert_same_reads(reads_before, _metric_reads(store))
    assert _latest_values(store) == latest_before


@pytest.mark.parametrize("fixture", PRE_RELEASE_FIXTURES)
def test_pre_release_fixture_reads_as_before_and_stops_at_revision_2(
    tmp_path: Path, fixture: str
) -> None:
    store, db_path = _fixture_store(tmp_path, fixture)
    rows = _legacy_rows(db_path)

    reads = _metric_reads(store)

    expected: dict[str, list[dict[str, Any]]] = {}
    for key, value, step, _ in rows:
        expected.setdefault(key, []).append({"value": value, "step": step})
    assert reads["data"] == expected
    assert read_experiment_schema(sqlite3.connect(db_path)).revision <= 2
    _assert_same_rows(rows, _legacy_rows(db_path))


def _revision2_db_with_rows(path: Path, rows: list[tuple[Any, ...]]) -> Path:
    build_revision2_db(path)
    conn = sqlite3.connect(path)
    conn.executemany(LEGACY_INSERT, rows)
    conn.commit()
    conn.close()
    return path


SAMPLE_ROWS = [
    ("loss", 1.5, 0, "2026-01-02 03:04:05"),
    ("loss", None, 1, "2026-01-02 03:04:06"),
    ("loss", float("inf"), 70, None),
    ("loss", float("-inf"), -5, "not a time"),
    ("acc", 0.25, 1000, "2026-01-02 03:04:07"),
    ("acc", b"\x00\x01", 1001, "2026-01-02 03:04:08"),
    ("acc", "text", 1002, "2026-01-02 03:04:09"),
]


def test_migration_converts_logged_at_and_keeps_storage_classes(tmp_path: Path) -> None:
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", SAMPLE_ROWS)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate()

    stored = conn.execute(
        "SELECT k.key, p.step, typeof(p.value), p.value, p.logged_ms "
        "FROM metric_points p JOIN metric_keys k ON k.id = p.metric_id"
    ).fetchall()
    by_step = {step: (cls, value, ms) for _, step, cls, value, ms in stored}
    assert by_step[0] == ("real", 1.5, 1767323045000)
    assert by_step[1][:2] == ("null", None)
    assert by_step[70][2] is None
    assert by_step[-5][2] is None
    assert by_step[1001][:2] == ("blob", b"\x00\x01")
    assert by_step[1002][:2] == ("text", "text")
    view = dict(conn.execute("SELECT step, logged_at FROM dynamic_metrics"))
    assert view[0] == "2026-01-02 03:04:05"
    assert view[70] is None
    assert_bucket_invariants(conn)
    conn.close()


def test_migration_round_trips_second_precision_timestamps(tmp_path: Path) -> None:
    stamps = [
        f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
        for year in (1970, 1999, 2026, 2100)
        for month, day in ((1, 1), (2, 28), (12, 31))
        for hour, minute, second in ((0, 0, 0), (13, 37, 59), (23, 59, 59))
    ]
    rows = [("t", float(step), step, stamp) for step, stamp in enumerate(stamps)]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate()
    view = conn.execute(
        "SELECT logged_at FROM dynamic_metrics ORDER BY step"
    ).fetchall()
    assert [row[0] for row in view] == stamps
    conn.close()


def test_migration_floors_fractional_seconds_to_milliseconds(tmp_path: Path) -> None:
    rows = [
        ("t", 0.0, 0, "2026-01-02 03:04:05.9999"),
        ("t", 1.0, 1, "2026-01-02T03:04:05.5Z"),
        ("t", 2.0, 2, "2026-01-02 03:04:05.123456+02:00"),
        ("t", 3.0, 3, "1969-12-31 23:59:59.25"),
    ]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate()
    stored = conn.execute(
        "SELECT logged_ms, logged_at FROM metric_points ORDER BY step"
    ).fetchall()
    conn.close()
    assert [ms for ms, _ in stored] == [
        1767323045999,
        1767323045500,
        1767315845123,
        -750,
    ]
    assert [at for _, at in stored[:3]] == [
        "2026-01-02 03:04:05",
        "2026-01-02 03:04:05",
        "2026-01-02 01:04:05",
    ]


def _numpy_step(step: int, size: int = 8) -> bytes:
    return step.to_bytes(size, "little", signed=True)


@pytest.mark.parametrize(
    ("row", "example"),
    [
        (("loss", 1.0, 2.5, None), "key 'loss', step 2.5"),
        (("loss", 1.0, "abc", None), "key 'loss', step 'abc'"),
        (("loss", 1.0, None, None), "key 'loss', step NULL"),
        (("loss", 1.0, b"\x01\x00\x00", None), "key 'loss', step X'010000'"),
        (("loss", 1.0, _numpy_step(-1, 4), None), "key 'loss', step X'FFFFFFFF'"),
        ((None, 1.0, 1, None), "key NULL, step 1"),
        ((b"loss", 1.0, 1, None), "key X'6C6F7373', step 1"),
    ],
)
def test_migration_refuses_rows_revision_3_cannot_store(
    tmp_path: Path, row: tuple[Any, ...], example: str
) -> None:
    db_path = _revision2_db_with_rows(
        tmp_path / "exp.db", [("ok", 1.0, 0, None), ("ok", 1.0, 1, None), row]
    )
    before = schema_snapshot(db_path)
    conn = sqlite3.connect(db_path)
    with pytest.raises(LegacyMetricRowsError) as raised:
        ExperimentMigrationRunner(conn).migrate()
    conn.close()
    assert (raised.value.count, raised.value.example) == (1, example)
    assert "stays at schema revision 2" in str(raised.value)
    assert schema_snapshot(db_path) == before


def test_migration_decodes_numpy_steps(tmp_path: Path) -> None:
    rows = [
        ("np", 0.5, _numpy_step(100), "2026-01-02 03:04:05"),
        ("np", 1.5, _numpy_step(-7), "2026-01-02 03:04:05"),
        ("np", 2.5, _numpy_step(2**63 - 1), None),
        # Decoded steps equal to stored ones: the later logged_at wins, on a tie
        # (or without times) the row that was an integer.
        ("dup", 10.0, 1, "2026-01-02 03:04:05"),
        ("dup", 11.0, _numpy_step(1), "2026-01-02 03:04:06"),
        ("dup", 20.0, 2, "2026-01-02 03:04:06"),
        ("dup", 21.0, _numpy_step(2), "2026-01-02 03:04:05"),
        ("dup", 30.0, 3, "2026-01-02 03:04:05"),
        ("dup", 31.0, _numpy_step(3, 4), "2026-01-02 03:04:05"),
        ("dup", 40.0, 4, None),
        ("dup", 41.0, _numpy_step(4), None),
        ("dup", 50.0, 5, None),
        ("dup", 51.0, _numpy_step(5), "2026-01-02 03:04:05"),
    ]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate()
    stored = conn.execute(
        "SELECT key, step, typeof(step), value FROM dynamic_metrics ORDER BY key, step"
    ).fetchall()
    assert stored == [
        ("dup", 1, "integer", 11.0),
        ("dup", 2, "integer", 20.0),
        ("dup", 3, "integer", 30.0),
        ("dup", 4, "integer", 40.0),
        ("dup", 5, "integer", 51.0),
        ("np", -7, "integer", 1.5),
        ("np", 100, "integer", 0.5),
        ("np", 2**63 - 1, "integer", 2.5),
    ]
    assert_bucket_invariants(conn)
    conn.close()


def test_migration_keeps_the_newer_of_two_colliding_numpy_steps(
    tmp_path: Path,
) -> None:
    rows = [
        ("a", 1.0, _numpy_step(9), "2026-01-02 03:04:06"),
        ("a", 2.0, _numpy_step(9, 4), "2026-01-02 03:04:05"),
        ("b", 1.0, _numpy_step(9), "2026-01-02 03:04:05"),
        ("b", 2.0, _numpy_step(9, 4), "2026-01-02 03:04:06"),
    ]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate()
    assert conn.execute(
        "SELECT key, step, value FROM dynamic_metrics ORDER BY key"
    ).fetchall() == [("a", 9, 1.0), ("b", 9, 2.0)]
    conn.close()


def test_failed_migration_leaves_revision_2_intact_and_usable(tmp_path: Path) -> None:
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", SAMPLE_ROWS)
    schema_before = schema_snapshot(db_path)
    rows_before = _legacy_rows(db_path)
    real_execute = sqlite3.Cursor.execute

    class FailingCursor(sqlite3.Cursor):
        def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:  # noqa: ANN401
            # The trigger comes last, after the old table was copied and dropped.
            if "CREATE TRIGGER" in sql:
                raise sqlite3.OperationalError("injected failure")
            return real_execute(self, sql, *args)

    class FailingConnection(sqlite3.Connection):
        def cursor(self, factory: Any = FailingCursor) -> Any:  # noqa: ANN401
            return super().cursor(factory)

    conn = sqlite3.connect(db_path, factory=FailingConnection)
    with pytest.raises(RuntimeError, match="injected failure"):
        ExperimentMigrationRunner(conn).migrate()
    conn.close()

    assert schema_snapshot(db_path) == schema_before
    _assert_same_rows(rows_before, _legacy_rows(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute(LEGACY_INSERT, ("loss", 9.0, 99, None))
    conn.commit()
    assert ExperimentMigrationRunner(conn).migrate() == [3, 4]
    assert_bucket_invariants(conn)
    conn.close()


def test_a_migration_that_ran_out_of_space_succeeds_on_the_same_connection(
    tmp_path: Path,
) -> None:
    rows = [
        ("k", float(step), _numpy_step(step) if step % 2 else step, None)
        for step in range(20_000)
    ]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    conn = sqlite3.connect(db_path)
    pages = conn.execute("PRAGMA page_count").fetchone()[0]
    # Room for the integer steps but not for the decoded ones: the disk fills while
    # the decode function is registered.
    conn.execute(f"PRAGMA max_page_count = {pages + 60}")
    with pytest.raises(RuntimeError, match="full"):
        ExperimentMigrationRunner(conn).migrate()
    conn.execute("PRAGMA max_page_count = 1073741823")

    assert ExperimentMigrationRunner(conn).migrate() == [3, 4]
    assert conn.execute(
        "SELECT count(*), min(step), max(step) FROM dynamic_metrics"
    ).fetchone() == (20_000, 0, 19_999)
    assert_bucket_invariants(conn)
    conn.close()


def test_migration_counts_values_beyond_the_summable_limit_only_in_count_and_range(
    tmp_path: Path,
) -> None:
    rows = [
        ("big", value, step, None)
        for step, value in enumerate(
            [1e290, -1e290, 5e295, -5e295, 1.7e308, float("inf"), None, 2.0]
        )
    ]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    conn = sqlite3.connect(db_path)
    ExperimentMigrationRunner(conn).migrate()
    assert conn.execute(
        "SELECT count, finite_count, min, max, sum FROM metric_buckets WHERE level = 3"
    ).fetchall() == [(8, 3, -5e295, float("inf"), 2.0)]
    assert_bucket_invariants(conn)
    conn.close()


def _migrate_in_child(db_path: str, start: Any, results: Any) -> None:  # noqa: ANN401
    conn = sqlite3.connect(db_path, timeout=30)
    start.wait()
    try:
        results.put(ExperimentMigrationRunner(conn).migrate())
    except Exception as error:  # noqa: BLE001
        results.put(repr(error))
    finally:
        conn.close()


def test_two_processes_migrating_at_once_migrate_once(tmp_path: Path) -> None:
    rows = [
        (f"m{key}", float(step), step, None) for key in range(5) for step in range(2000)
    ]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    results = context.Queue()
    children = [
        context.Process(target=_migrate_in_child, args=(str(db_path), start, results))
        for _ in range(3)
    ]
    for child in children:
        child.start()
    start.set()
    outcomes = [results.get(timeout=60) for _ in children]
    for child in children:
        child.join(60)

    assert sorted(outcomes, key=len) == [[], [], [3, 4]]
    conn = sqlite3.connect(db_path)
    assert conn.execute(
        "SELECT version FROM exp_schema_migrations ORDER BY version"
    ).fetchall() == [(1,), (2,), (3,), (4,)]
    assert conn.execute("SELECT count(*) FROM metric_points").fetchone()[0] == len(rows)
    assert_bucket_invariants(conn)
    conn.close()


def test_reader_open_during_migration_keeps_reading(tmp_path: Path) -> None:
    rows = [("loss", float(step), step, None) for step in range(500)]
    db_path = _revision2_db_with_rows(tmp_path / "exp.db", rows)
    reader = sqlite3.connect(db_path, check_same_thread=False)
    reader.execute("BEGIN")
    snapshot = reader.execute("SELECT count(*) FROM dynamic_metrics").fetchone()

    migrated = threading.Event()

    def migrate() -> None:
        conn = sqlite3.connect(db_path)
        ExperimentMigrationRunner(conn).migrate()
        conn.close()
        migrated.set()

    worker = threading.Thread(target=migrate)
    worker.start()
    worker.join(30)
    assert migrated.is_set()
    # The open read transaction still sees its snapshot of revision 2.
    assert reader.execute("SELECT count(*) FROM dynamic_metrics").fetchone() == snapshot
    reader.rollback()
    assert reader.execute(
        "SELECT value, step FROM dynamic_metrics ORDER BY step"
    ).fetchall() == [(value, step) for _, value, step, _ in rows]
    reader.close()


def test_known_revision_matches_the_newest_migration() -> None:
    conn = sqlite3.connect(":memory:")
    migrations = ExperimentMigrationRunner(conn)._discover_migrations()
    assert migrations[-1]["version"] == KNOWN_EXPERIMENT_REVISION
