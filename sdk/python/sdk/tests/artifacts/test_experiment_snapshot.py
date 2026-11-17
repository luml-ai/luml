import contextlib
import errno
import io
import json
import logging
import os
import signal
import sqlite3
import subprocess
import sys
import tarfile
import threading
import time
import tracemalloc
import warnings
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from luml import ExperimentReference
from luml.artifacts._base import DiskFile
from luml.artifacts.model import ModelReference
from luml.experiments.backends import _snapshot
from luml.experiments.backends._exceptions import ExportSpaceError
from luml.experiments.backends._snapshot import WORK_DIR_PREFIX
from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.tracker import ExperimentTracker
from tests.artifacts.snapshot_helpers import (
    assert_publishable_db,
    connect_read_only,
    copy_with_layout,
    extract_snapshot_db,
    live_database_state,
    read_json_member,
    schema_objects,
    table_rows,
)
from tests.experiments.metric_helpers import (
    FIXTURES_DIR,
    LEGACY_INSERT,
    assert_bucket_invariants,
    make_revision2_store,
)

EXP_ID = "exp"
SDK_ROOT = Path(__file__).parents[2]
FORK_TIMEOUT = 60


def _tracker(store: Path, flush_interval: float = 0.5) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{store}", flush_interval=flush_interval)


def _populate(tracker: ExperimentTracker) -> None:
    tracker.start_experiment(name="snap", experiment_id=EXP_ID, tags=["a"])
    tracker.log_static("lr", 0.1)
    tracker.log_static("layers", [64, 32])
    for step in range(300):
        tracker.log_dynamic("loss", 1.0 / (step + 1), step=step)
        tracker.log_dynamic("acc/top1", step * 0.01, step=step * 7 - 500)
    tracker.log_dynamic("loss", float("inf"), step=1000)
    tracker.log_dynamic("loss", float("nan"), step=1001)
    tracker.log_dynamic("loss", 0.25, step=5)
    tracker.log_attachment("notes.txt", "hello")
    tracker.log_span("t1", "s1", "root", 1, 2, attributes={"x": 1})
    tracker.log_eval_sample("ev1", "ds", {"q": "x"}, {"a": "y"}, scores={"acc": 1.0})
    tracker.link_eval_sample_to_trace("ds", "ev1", "t1")
    tracker.log_eval_annotation("ds", "ev1", "good", "feedback", "bool", True, "u")
    tracker.end_experiment(EXP_ID)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "store"


@pytest.fixture
def tracker(store: Path) -> ExperimentTracker:
    tracker = _tracker(store)
    _populate(tracker)
    return tracker


def _db_path(store: Path) -> Path:
    return store / EXP_ID / "exp.db"


def _work_dirs(store: Path) -> list[Path]:
    return sorted((store / EXP_ID).glob(f"{WORK_DIR_PREFIX}*"))


def _pooled_paths(tracker: ExperimentTracker) -> list[str]:
    stats = tracker.backend.pool.get_stats()  # type: ignore[attr-defined]
    return sorted(Path(path).name for path in stats["connections"])


def _rows_of(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    conn = connect_read_only(path)
    try:
        return table_rows(conn)
    finally:
        conn.close()


def _rows_without_migration_times(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    """Rows to compare between two migrations of the same data: each migration records
    the wall-clock time it ran at."""
    rows = _rows_of(path)
    rows["exp_schema_migrations"] = [
        (version,) for version, *_ in rows["exp_schema_migrations"]
    ]
    return rows


def _objects_of(path: Path) -> list[tuple[str, str, str | None]]:
    conn = connect_read_only(path)
    try:
        return schema_objects(conn)
    finally:
        conn.close()


def _check_invariants(path: Path) -> None:
    conn = connect_read_only(path)
    try:
        assert_bucket_invariants(conn)
    finally:
        conn.close()


def _manifest(artifact: Path) -> dict[str, Any]:
    return read_json_member(artifact, "manifest.json")


def _tar_layout(artifact: Path) -> list[tuple[str, int, int, str, str, int]]:
    with tarfile.open(artifact) as tar:
        return [
            (m.name, m.uid, m.gid, m.uname, m.gname, int(m.mtime))
            for m in tar.getmembers()
        ]


def _embedded_names(model: Path) -> tuple[str, list[str]]:
    with tarfile.open(model) as tar:
        names = tar.getnames()
    (meta,) = [name for name in names if name.startswith("meta-")]
    return meta, [name for name in names if name.startswith("meta_artifacts/")]


def _revision2_store(store: Path, rows: list[tuple[Any, ...]]) -> Path:
    db_path = make_revision2_store(store, EXP_ID)
    conn = sqlite3.connect(db_path)
    conn.executemany(LEGACY_INSERT, rows)
    conn.execute(
        "INSERT INTO static_params (key, value, value_type) "
        "VALUES ('lr', '0.1', 'float')"
    )
    conn.commit()
    conn.close()
    return db_path


REVISION2_ROWS = [
    ("loss", float(step) / 10, step, "2026-01-02 03:04:05") for step in range(200)
] + [
    ("acc", 0.5, -3, None),
    ("acc", float("inf"), 9, "2026-01-02 03:04:06.123"),
    ("acc", None, 10, None),
    ("np", 1.0, (77).to_bytes(8, "little", signed=True), None),
]


def test_standalone_artifact_is_generation_2_and_round_trips(
    tracker: ExperimentTracker, store: Path, tmp_path: Path
) -> None:
    artifact = tmp_path / "exp.tar"
    before = live_database_state(_db_path(store))

    ref = tracker.export(str(artifact), experiment_id=EXP_ID)

    assert [entry[0] for entry in _tar_layout(artifact)] == [
        "manifest.json",
        "exp.db",
        "attachments.tar",
        "attachments.index.json",
    ]
    assert all(entry[1:] == (0, 0, "", "", 0) for entry in _tar_layout(artifact)[:2])
    manifest = _manifest(artifact)
    assert manifest["producer_tags"] == ["luml.ai::experiment_snapshot:v2"]
    assert manifest["payload"] == {
        "local_experiment_id": EXP_ID,
        "status": "completed",
        "group": manifest["payload"]["group"],
        "tags": ["a"],
        "schema_revision": 3,
        "min_reader_revision": 2,
    }
    assert ref.validate()
    assert ref.snapshot_member() == "exp.db"

    snapshot = tmp_path / "snapshot.db"
    assert extract_snapshot_db(artifact, snapshot) == "exp.db"
    assert_publishable_db(snapshot)
    _check_invariants(snapshot)
    assert _objects_of(snapshot) == before["schema"]
    assert _rows_of(snapshot) == before["rows"]
    assert live_database_state(_db_path(store)) == before
    assert _work_dirs(store) == []


def test_embedded_snapshot_is_generation_2_and_round_trips(
    tracker: ExperimentTracker, store: Path, dummy_model_file: Path, tmp_path: Path
) -> None:
    before = live_database_state(_db_path(store))

    tracker.link_to_model(ModelReference(str(dummy_model_file)), EXP_ID)

    meta, members = _embedded_names(dummy_model_file)
    prefix = "meta_artifacts/dataforce.studio~c~~c~experiment_snapshot~c~v2~~et~~"
    snapshot_id = members[0].removeprefix(prefix).split("/")[0]
    assert members == [
        f"{prefix}{snapshot_id}/exp.db",
        f"{prefix}{snapshot_id}/attachments.tar",
        f"{prefix}{snapshot_id}/attachments.index.json",
    ]
    assert read_json_member(dummy_model_file, meta) == [
        {
            "id": f"dataforce.studio~c~~c~experiment_snapshot~c~v2~~et~~{snapshot_id}",
            "tags": ["dataforce.studio::experiment_snapshot:v2"],
            "payload": {},
        }
    ]
    snapshot = tmp_path / "snapshot.db"
    extract_snapshot_db(dummy_model_file, snapshot)
    assert_publishable_db(snapshot)
    assert _rows_of(snapshot) == before["rows"]
    assert live_database_state(_db_path(store)) == before
    assert _work_dirs(store) == []


def test_snapshot_keeps_each_metric_contiguous(store: Path, tmp_path: Path) -> None:
    tracker = _tracker(store, flush_interval=3600)
    tracker.start_experiment(experiment_id=EXP_ID)
    for step in range(15_000):
        for key in ("a", "b", "c"):
            tracker.log_dynamic(key, step * 0.5, step=step)
        if step % 50 == 0:
            tracker.backend.flush(EXP_ID)
    tracker.end_experiment(EXP_ID)
    artifact = tmp_path / "exp.tar"
    tracker.export(str(artifact), experiment_id=EXP_ID)
    snapshot = tmp_path / "snapshot.db"
    extract_snapshot_db(artifact, snapshot)
    live = copy_with_layout(_db_path(store), tmp_path / "live.db")

    for metric_id, pages in _metric_point_pages(snapshot).items():
        span = max(pages) - min(pages) + 1
        # Interior pages may sit between leaves; nothing of another metric does.
        assert span <= len(pages) + 2, (metric_id, sorted(pages))
        assert len(pages) <= _pages_needed(snapshot, 15_000) + 1
    live_spans = [
        max(pages) - min(pages) + 1 - len(pages)
        for pages in _metric_point_pages(live).values()
    ]
    assert max(live_spans) > 50, "the live layout should interleave the metrics"


def _varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for offset in range(9):
        byte = data[pos + offset]
        if offset == 8:
            return (value << 8) | byte, pos + 9
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, pos + offset + 1
    raise AssertionError("unreachable")


_INT_SIZES = {1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 8}


def _btree_leaves(data: bytes, page_size: int, page_no: int) -> list[int]:
    """Leaf page numbers of a b-tree in key order (SQLite file format, section 1.6)."""
    page = data[(page_no - 1) * page_size : page_no * page_size]
    header = 100 if page_no == 1 else 0
    kind = page[header]
    if kind in (10, 13):
        return [page_no]
    cells = int.from_bytes(page[header + 3 : header + 5], "big")
    pointers = [
        int.from_bytes(page[header + 12 + 2 * i : header + 14 + 2 * i], "big")
        for i in range(cells)
    ]
    children = [int.from_bytes(page[p : p + 4], "big") for p in pointers]
    children.append(int.from_bytes(page[header + 8 : header + 12], "big"))
    return [
        leaf for child in children for leaf in _btree_leaves(data, page_size, child)
    ]


def _leaf_metric_ids(page: bytes) -> list[int]:
    """The first key column of every cell of a WITHOUT ROWID leaf page."""
    cells = int.from_bytes(page[3:5], "big")
    ids = []
    for i in range(cells):
        pos = int.from_bytes(page[8 + 2 * i : 10 + 2 * i], "big")
        _, pos = _varint(page, pos)
        header_size, body = _varint(page, pos)
        serial_type, _ = _varint(page, body)
        start = pos + header_size
        if serial_type in (8, 9):
            ids.append(serial_type - 8)
        else:
            size = _INT_SIZES[serial_type]
            ids.append(int.from_bytes(page[start : start + size], "big", signed=True))
    return ids


def _metric_point_pages(path: Path) -> dict[int, set[int]]:
    data = path.read_bytes()
    page_size = int.from_bytes(data[16:18], "big")
    conn = connect_read_only(path)
    root = conn.execute(
        "SELECT rootpage FROM sqlite_master WHERE name = 'metric_points'"
    ).fetchone()[0]
    conn.close()
    pages: dict[int, set[int]] = {}
    for leaf in _btree_leaves(data, page_size, root):
        page = data[(leaf - 1) * page_size : leaf * page_size]
        for metric_id in _leaf_metric_ids(page):
            pages.setdefault(metric_id, set()).add(leaf)
    return pages


def _pages_needed(path: Path, rows: int) -> int:
    data = path.read_bytes()
    page_size = int.from_bytes(data[16:18], "big")
    conn = connect_read_only(path)
    root = conn.execute(
        "SELECT rootpage FROM sqlite_master WHERE name = 'metric_points'"
    ).fetchone()[0]
    total = conn.execute("SELECT count(*) FROM metric_points").fetchone()[0]
    conn.close()
    leaves = _btree_leaves(data, page_size, root)
    rows_per_page = total / len(leaves)
    return -(-rows // int(rows_per_page))


def test_revision_2_store_is_migrated_in_the_copy_only(
    store: Path, tmp_path: Path
) -> None:
    db_path = _revision2_store(store, REVISION2_ROWS)
    before = live_database_state(db_path)
    tracker = _tracker(store)
    artifact = tmp_path / "exp.tar"

    tracker.export(str(artifact), experiment_id=EXP_ID)
    tracker.backend.close()

    manifest = _manifest(artifact)
    assert manifest["producer_tags"] == ["luml.ai::experiment_snapshot:v2"]
    assert manifest["payload"]["schema_revision"] == 3
    snapshot = tmp_path / "snapshot.db"
    assert extract_snapshot_db(artifact, snapshot) == "exp.db"
    assert_publishable_db(snapshot)
    _check_invariants(snapshot)
    expected = tmp_path / "expected.db"
    copy_with_layout(db_path, expected)
    conn = sqlite3.connect(expected)
    assert ExperimentMigrationRunner(conn).migrate() == [3]
    conn.close()
    assert _rows_without_migration_times(snapshot) == _rows_without_migration_times(
        expected
    )
    assert _objects_of(snapshot) == _objects_of(expected)
    assert live_database_state(db_path) == before
    assert before["user_version"] == 2


def test_rows_revision_3_cannot_store_fall_back_to_generation_1(
    store: Path,
    tmp_path: Path,
    dummy_model_file: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_path = _revision2_store(store, [*REVISION2_ROWS, ("loss", 7.0, 2.5, None)])
    before = live_database_state(db_path)
    tracker = _tracker(store)
    artifact = tmp_path / "exp.tar"

    with caplog.at_level(logging.WARNING):
        ref = tracker.export(str(artifact), experiment_id=EXP_ID)
        tracker.link_to_model(ModelReference(str(dummy_model_file)), EXP_ID)

    warnings_logged = [r.getMessage() for r in caplog.records]
    assert len(warnings_logged) == 2
    assert all("key 'loss', step 2.5" in message for message in warnings_logged)
    assert [entry[0] for entry in _tar_layout(artifact)] == [
        "manifest.json",
        "exp.db.zip",
        "attachments.tar",
        "attachments.index.json",
    ]
    manifest = _manifest(artifact)
    assert manifest["producer_tags"] == ["luml.ai::experiment_snapshot:v1"]
    assert sorted(manifest["payload"]) == [
        "group",
        "local_experiment_id",
        "status",
        "tags",
    ]
    assert ref.validate()
    assert ref.snapshot_member() == "exp.db.zip"
    with zipfile.ZipFile(io.BytesIO(_read(artifact, "exp.db.zip"))) as archive:
        assert archive.namelist() == ["exp.db"]
    snapshot = tmp_path / "snapshot.db"
    extract_snapshot_db(artifact, snapshot)
    assert _rows_of(snapshot) == before["rows"]
    assert _objects_of(snapshot) == before["schema"]

    meta, members = _embedded_names(dummy_model_file)
    assert read_json_member(dummy_model_file, meta)[0]["tags"] == [
        "dataforce.studio::experiment_snapshot:v1"
    ]
    assert members[0].endswith("/exp.db.zip")
    assert "experiment_snapshot~c~v1~~et~~" in members[0]
    embedded = tmp_path / "embedded.db"
    extract_snapshot_db(dummy_model_file, embedded)
    assert _rows_of(embedded) == before["rows"]
    assert live_database_state(db_path) == before
    assert _work_dirs(store) == []


def _read(artifact: Path, name: str) -> bytes:
    with tarfile.open(artifact) as tar:
        extracted = tar.extractfile(name)
        assert extracted is not None
        return extracted.read()


def test_export_leaves_the_pooled_connection_as_it_was(
    tracker: ExperimentTracker, store: Path, tmp_path: Path
) -> None:
    pragmas = (
        "page_size",
        "journal_mode",
        "foreign_keys",
        "synchronous",
        "journal_size_limit",
        "busy_timeout",
        "database_list",
    )

    def connection_state() -> list[list[tuple[Any, ...]]]:
        with tracker.backend.pool.get_connection(_db_path(store)) as conn:  # type: ignore[attr-defined]
            return [conn.execute(f"PRAGMA {name}").fetchall() for name in pragmas]

    before = connection_state()
    tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)

    assert connection_state() == before
    assert _pooled_paths(tracker) == ["exp.db", "meta.db"]


def test_the_live_database_cannot_be_written_through_the_export(
    tracker: ExperimentTracker,
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = str(_db_path(store).resolve())
    write_errors: list[str] = []
    original = _snapshot._helper_connection

    @contextlib.contextmanager
    def probing(pool: Any, work_dir: Path) -> Iterator[sqlite3.Connection]:  # noqa: ANN401
        with original(pool, work_dir) as conn:
            yield conn
            for _, schema, path in conn.execute("PRAGMA database_list").fetchall():
                if path and str(Path(path).resolve()) == live:
                    try:
                        conn.execute(f"CREATE TABLE {schema}.probe (x)")
                        write_errors.append("written")
                    except sqlite3.OperationalError as error:
                        write_errors.append(str(error))

    monkeypatch.setattr(_snapshot, "_helper_connection", probing)
    tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)

    assert write_errors == ["attempt to write a readonly database"]


def _log_until(
    tracker: ExperimentTracker, key: str, stop: threading.Event, errors: list[str]
) -> None:
    step = 0
    try:
        while not stop.is_set():
            tracker.log_dynamic(key, step * 0.5, step=step, experiment_id=EXP_ID)
            if step % 3 == 0:
                tracker.log_dynamic(key, -1.0, step=step // 2, experiment_id=EXP_ID)
            if step % 50 == 0:
                tracker.log_span(
                    f"t-{key}", f"s{step}", "op", 1, 2, experiment_id=EXP_ID
                )
            step += 1
    except Exception as error:  # noqa: BLE001
        errors.append(repr(error))


def _assert_consistent_snapshot(artifact: Path, dest: Path) -> int:
    extract_snapshot_db(artifact, dest)
    assert_publishable_db(dest)
    _check_invariants(dest)
    conn = connect_read_only(dest)
    try:
        return conn.execute("SELECT count(*) FROM metric_points").fetchone()[0]
    finally:
        conn.close()


def test_export_while_threads_log_is_consistent(
    tracker: ExperimentTracker, store: Path, tmp_path: Path
) -> None:
    stop = threading.Event()
    errors: list[str] = []
    writers = [
        threading.Thread(target=_log_until, args=(tracker, key, stop, errors))
        for key in ("w1", "w2", "w3")
    ]
    for writer in writers:
        writer.start()
    counts = []
    try:
        for attempt in range(6):
            artifact = tmp_path / f"exp{attempt}.tar"
            tracker.export(str(artifact), experiment_id=EXP_ID)
            counts.append(
                _assert_consistent_snapshot(artifact, tmp_path / f"{attempt}.db")
            )
            time.sleep(0.05)
    finally:
        stop.set()
        for writer in writers:
            writer.join()
    assert errors == []
    assert counts == sorted(counts)
    assert counts[-1] > counts[0]
    tracker.export(str(tmp_path / "final.tar"), experiment_id=EXP_ID)
    final = _assert_consistent_snapshot(tmp_path / "final.tar", tmp_path / "final.db")
    assert final == _rows_count(_db_path(store), "metric_points")
    _check_invariants(_db_path(store))


def _rows_count(path: Path, table: str) -> int:
    conn = connect_read_only(path)
    try:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


OTHER_PROCESS_WRITER = """
import sys
from luml.experiments.backends.sqlite import SQLiteBackend
backend = SQLiteBackend(sys.argv[1], flush_interval=0.01)
print("ready", flush=True)
for step in range(int(sys.argv[2])):
    backend.log_dynamic("exp", "proc", step * 0.5, step=step)
    backend.log_dynamic("exp", "proc", -1.0, step=step // 3)
    if step % 100 == 0:
        backend.log_span("exp", "tp", f"s{step}", "op", 1, 2)
backend.close()
print("done", flush=True)
"""


def test_export_while_another_process_logs_is_consistent(
    tracker: ExperimentTracker, store: Path, tmp_path: Path
) -> None:
    steps = 6000
    writer = subprocess.Popen(
        [sys.executable, "-c", OTHER_PROCESS_WRITER, str(store), str(steps)],
        cwd=SDK_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert writer.stdout is not None
    assert writer.stdout.readline().strip() == "ready"
    exports = 0
    while writer.poll() is None:
        artifact = tmp_path / f"exp{exports}.tar"
        tracker.export(str(artifact), experiment_id=EXP_ID)
        _assert_consistent_snapshot(artifact, tmp_path / f"{exports}.db")
        exports += 1
    _, stderr = writer.communicate(timeout=120)
    assert writer.returncode == 0, stderr
    assert exports >= 2

    tracker.export(str(tmp_path / "final.tar"), experiment_id=EXP_ID)
    _assert_consistent_snapshot(tmp_path / "final.tar", tmp_path / "final.db")
    conn = connect_read_only(tmp_path / "final.db")
    assert conn.execute(
        "SELECT count(*), min(step), max(step) FROM dynamic_metrics WHERE key = 'proc'"
    ).fetchone() == (steps, 0, steps - 1)
    conn.close()


def test_export_memory_stays_far_below_the_database_size(
    store: Path, tmp_path: Path, dummy_model_file: Path
) -> None:
    tracker = _tracker(store)
    tracker.start_experiment(experiment_id=EXP_ID)
    block = "x" * 100_000
    for index in range(320):
        tracker.log_span("t", f"s{index}", "op", 1, 2, attributes={"text": block})
    for step in range(20_000):
        tracker.log_dynamic("loss", step * 0.5, step=step)
    tracker.end_experiment(EXP_ID)
    tracker.backend.flush(EXP_ID)
    assert _db_path(store).stat().st_size > 30_000_000

    tracemalloc.start()
    try:
        tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)
        _, export_peak = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        tracker.link_to_model(ModelReference(str(dummy_model_file)), EXP_ID)
        _, link_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert export_peak < 3_000_000, export_peak
    assert link_peak < 3_000_000, link_peak
    assert (tmp_path / "exp.tar").stat().st_size > 30_000_000


class _InjectedError(Exception):
    pass


def _fail_on_call(
    monkeypatch: pytest.MonkeyPatch, owner: object, name: str, call: int
) -> None:
    original = getattr(owner, name)
    calls = [0]

    def failing(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        calls[0] += 1
        if calls[0] == call:
            raise _InjectedError(name)
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, failing)


@pytest.mark.parametrize(
    ("owner", "name", "call"),
    [
        (_snapshot, "_vacuum_into", 1),
        (_snapshot, "_read_schema", 1),
        (_snapshot.shutil, "copyfile", 1),
        (_snapshot, "_migrate", 1),
        (_snapshot, "_vacuum_into", 2),
        (_snapshot, "_read_schema", 2),
        (ExperimentTracker, "export_attachments", 1),
        (zipfile.ZipFile, "write", 1),
        (DiskFile, "add_to_tar", 1),
    ],
    ids=[
        "copy",
        "read-copy-revision",
        "duplicate-copy",
        "migrate",
        "compact",
        "read-revision",
        "attachments",
        "zip",
        "write-artifact",
    ],
)
def test_a_failure_at_any_stage_leaves_nothing_behind(
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner: object,
    name: str,
    call: int,
) -> None:
    falls_back = owner is zipfile.ZipFile
    rows = REVISION2_ROWS + ([("loss", 7.0, 2.5, None)] if falls_back else [])
    db_path = _revision2_store(store, rows)
    before = live_database_state(db_path)
    tracker = _tracker(store)
    if owner is ExperimentTracker:
        owner = tracker.backend
    _fail_on_call(monkeypatch, owner, name, call)
    artifact = tmp_path / "exp.tar"

    with pytest.raises(_InjectedError):
        tracker.export(str(artifact), experiment_id=EXP_ID)

    assert _work_dirs(store) == []
    assert not artifact.exists()
    assert _pooled_paths(tracker) == ["exp.db", "meta.db"]
    assert live_database_state(db_path) == before
    monkeypatch.undo()
    tracker.export(str(artifact), experiment_id=EXP_ID)
    assert ExperimentReference(str(artifact)).validate()


def test_a_failed_embed_leaves_the_model_archive_as_it_was(
    tracker: ExperimentTracker,
    store: Path,
    dummy_model_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tarfile.open(dummy_model_file) as tar:
        before = [(m.name, tar.extractfile(m).read()) for m in tar]  # type: ignore[union-attr]
    _fail_on_call(monkeypatch, DiskFile, "add_to_tar", 2)

    with pytest.raises(_InjectedError):
        tracker.link_to_model(ModelReference(str(dummy_model_file)), EXP_ID)

    with tarfile.open(dummy_model_file) as tar:
        after = [(m.name, tar.extractfile(m).read()) for m in tar]  # type: ignore[union-attr]
    assert after == before
    assert _work_dirs(store) == []


# Above the largest pid Linux hands out (2**22).
DEAD_PID = 99999999


def _leftover(
    store: Path, name: str, age_seconds: float, with_lock_file: bool = True
) -> Path:
    leftover = store / EXP_ID / f"{WORK_DIR_PREFIX}{name}"
    leftover.mkdir()
    (leftover / "copy.db").write_bytes(b"partial")
    if with_lock_file:
        (leftover / _snapshot.WORK_DIR_LOCK).touch()
    mtime = time.time() - age_seconds
    os.utime(leftover, (mtime, mtime))
    return leftover


@pytest.mark.skipif(sys.platform == "win32", reason="needs flock")
def test_leftovers_of_dead_exporters_are_removed(
    tracker: ExperimentTracker, store: Path, tmp_path: Path
) -> None:
    hour, day = 3600, 24 * 3600
    _leftover(store, f"{DEAD_PID}-old", 2 * hour)
    _leftover(store, f"{DEAD_PID}-unlocked-old", 2 * day, with_lock_file=False)
    kept = [
        _leftover(store, f"{os.getppid()}-alive", 2 * day),
        _leftover(store, f"{DEAD_PID}-recent", hour / 2),
        _leftover(store, f"{DEAD_PID}-unlocked", 2 * hour, with_lock_file=False),
    ]

    tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)

    assert _work_dirs(store) == sorted(kept)


PAUSED_EXPORT = """
import sys
from luml.experiments.backends import _snapshot
from luml.experiments.tracker import ExperimentTracker
build = _snapshot._build_snapshot
def paused(*args):
    snapshot = build(*args)
    print(snapshot.work_dir, flush=True)
    sys.stdin.readline()
    return snapshot
_snapshot._build_snapshot = paused
ExperimentTracker("sqlite://" + sys.argv[1]).export(sys.argv[2], experiment_id="exp")
print("done", flush=True)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="needs flock")
def test_a_live_export_whose_pid_is_not_visible_keeps_its_work_dir(
    tracker: ExperimentTracker,
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker.backend.close()
    artifact = tmp_path / "exp.tar"
    exporter = subprocess.Popen(
        [sys.executable, "-c", PAUSED_EXPORT, str(store), str(artifact)],
        cwd=SDK_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert exporter.stdin is not None
    assert exporter.stdout is not None
    work_dir = Path(exporter.stdout.readline().strip())
    two_days_ago = time.time() - 2 * 24 * 3600
    os.utime(work_dir, (two_days_ago, two_days_ago))
    # As os.kill answers for a pid of another pid namespace or host.
    monkeypatch.setattr(_snapshot, "_process_exists", lambda pid: False)

    _snapshot.remove_abandoned_work_dirs(store / EXP_ID)

    assert sorted(path.name for path in work_dir.iterdir()) == [
        ".lock",
        "copy.db",
        "helper.db",
    ]
    exporter.stdin.write("\n")
    exporter.stdin.flush()
    stdout, stderr = exporter.communicate(timeout=FORK_TIMEOUT)
    assert exporter.returncode == 0, stderr
    assert stdout.strip() == "done"
    assert ExperimentReference(str(artifact)).validate()
    assert _work_dirs(store) == []


SPACE_LIMITED_EXPORT = """
import json, resource, signal, sys
from pathlib import Path
from luml.experiments.tracker import ExperimentTracker
store, artifact, limit = sys.argv[1], sys.argv[2], int(sys.argv[3])
tracker = ExperimentTracker("sqlite://" + store)
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
try:
    tracker.export(artifact, experiment_id="exp")
    result = {"error": None}
except Exception as error:
    result = {"error": type(error).__name__, "message": str(error)}
result["left"] = sorted(p.name for p in (Path(store) / "exp").iterdir())
print(json.dumps(result))
"""


@pytest.mark.skipif(sys.platform != "linux", reason="needs RLIMIT_FSIZE")
def test_a_write_error_during_export_leaves_nothing_behind(
    store: Path, tmp_path: Path
) -> None:
    tracker = _tracker(store)
    tracker.start_experiment(experiment_id=EXP_ID)
    tracker.log_static("blob", "x" * 3_000_000)
    tracker.end_experiment(EXP_ID)
    tracker.backend.close()
    left_before = sorted(p.name for p in (store / EXP_ID).iterdir())

    # Writes past 1 MB fail with EFBIG, which SQLite reports as an I/O error.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            SPACE_LIMITED_EXPORT,
            str(store),
            str(tmp_path / "exp.tar"),
            str(1_000_000),
        ],
        cwd=SDK_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcome["error"] == "OperationalError", outcome
    assert [name for name in outcome["left"] if name.startswith(WORK_DIR_PREFIX)] == []
    assert set(outcome["left"]) - {"exp.db-wal", "exp.db-shm"} == set(left_before)
    assert not (tmp_path / "exp.tar").exists()


def _disk_full() -> sqlite3.OperationalError:
    error = sqlite3.OperationalError("database or disk is full")
    error.sqlite_errorcode = sqlite3.SQLITE_FULL  # type: ignore[attr-defined]
    return error


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("_vacuum_into", _disk_full()),
        ("_migrate", RuntimeError("Migration 3 failed")),
        ("copyfile", OSError(errno.ENOSPC, "No space left on device")),
    ],
)
def test_a_full_disk_gives_a_clear_error_and_leaves_nothing(
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    error: Exception,
) -> None:
    db_path = _revision2_store(store, REVISION2_ROWS)
    before = live_database_state(db_path)
    tracker = _tracker(store)
    if name == "_migrate":
        error.__cause__ = _disk_full()
    owner = _snapshot.shutil if name == "copyfile" else _snapshot

    def full(*args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        raise error

    monkeypatch.setattr(owner, name, full)

    with pytest.raises(ExportSpaceError, match="Not enough disk space") as raised:
        tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)

    assert raised.value.__cause__ is error
    assert _work_dirs(store) == []
    assert not (tmp_path / "exp.tar").exists()
    assert live_database_state(db_path) == before


def test_experiment_reference_accepts_both_generations(
    tracker: ExperimentTracker, tmp_path: Path
) -> None:
    generation_2 = tracker.export(str(tmp_path / "exp.tar"), experiment_id=EXP_ID)
    references = {
        "d_sdk_0_5_0": "exp.db.zip",
        "g_raw_sdk_0_5_0": "exp.db",
    }
    for name, member in references.items():
        reference = ExperimentReference(str(FIXTURES_DIR / f"{name}.tar"))
        assert reference.validate(), name
        assert reference.snapshot_member() == member
        assert reference.get_manifest().payload.schema_revision is None
    assert generation_2.validate()
    assert generation_2.get_manifest().payload.schema_revision == 3

    without_database = tmp_path / "no-db.tar"
    with tarfile.open(without_database, "w") as tar:
        manifest = _read(tmp_path / "exp.tar", "manifest.json")
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest)
        tar.addfile(info, io.BytesIO(manifest))
    assert not ExperimentReference(str(without_database)).validate()


@contextlib.contextmanager
def _slow_snapshot_copy(
    monkeypatch: pytest.MonkeyPatch,
    copying: threading.Event,
    copied: threading.Event | None = None,
) -> Iterator[None]:
    """Slows down the first copy of an export, which holds its helper connection."""
    original = _snapshot._helper_connection

    @contextlib.contextmanager
    def slow(pool: Any, work_dir: Path) -> Iterator[sqlite3.Connection]:  # noqa: ANN401
        first = not copying.is_set()
        with original(pool, work_dir) as conn:
            if first:
                conn.set_progress_handler(lambda: time.sleep(0.005) or 0, 200)
                copying.set()
            yield conn
        if first and copied is not None:
            copied.set()

    monkeypatch.setattr(_snapshot, "_helper_connection", slow)
    yield


def _fork(child: Callable[[], bool]) -> int:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        pid = os.fork()
    if pid == 0:
        exit_code = 1
        try:
            signal.alarm(FORK_TIMEOUT)
            if child():
                exit_code = 0
        finally:
            os._exit(exit_code)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


def test_logging_and_reading_are_not_blocked_by_a_running_export(
    tracker: ExperimentTracker,
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copying, copied = threading.Event(), threading.Event()
    artifact = tmp_path / "exp.tar"

    with _slow_snapshot_copy(monkeypatch, copying, copied):
        exporter = threading.Thread(
            target=tracker.export,
            args=(str(artifact),),
            kwargs={"experiment_id": EXP_ID},
        )
        exporter.start()
        assert copying.wait(30)
        tracker.log_dynamic("during", 1.0, step=0, experiment_id=EXP_ID)
        tracker.backend.flush(EXP_ID)
        history = tracker.backend.get_experiment_metric_history(EXP_ID, "during")
        still_copying = not copied.is_set()
        exporter.join(FORK_TIMEOUT)

    assert [point["value"] for point in history] == [1.0]
    assert still_copying
    assert ExperimentReference(str(artifact)).validate()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
def test_fork_while_an_export_runs(
    tracker: ExperimentTracker,
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copying = threading.Event()
    artifact = tmp_path / "exp.tar"
    outcome: list[object] = []

    def export() -> None:
        try:
            outcome.append(tracker.export(str(artifact), experiment_id=EXP_ID))
        except Exception as error:  # noqa: BLE001
            outcome.append(error)

    def child() -> bool:
        tracker.log_dynamic("child", 1.0, step=0, experiment_id=EXP_ID)
        tracker.backend.flush(EXP_ID)
        conn = connect_read_only(_db_path(store))
        try:
            return conn.execute(
                "SELECT count(*) FROM dynamic_metrics WHERE key = 'child'"
            ).fetchone() == (1,)
        finally:
            conn.close()

    with _slow_snapshot_copy(monkeypatch, copying):
        exporter = threading.Thread(target=export)
        exporter.start()
        assert copying.wait(30)
        exit_code = _fork(child)
        exporter.join(FORK_TIMEOUT)

    assert exit_code == 0
    assert not exporter.is_alive()
    assert isinstance(outcome[0], ExperimentReference), outcome
    snapshot = tmp_path / "snapshot.db"
    extract_snapshot_db(artifact, snapshot)
    assert_publishable_db(snapshot)


def _is_open(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")
def test_a_forked_child_neither_releases_nor_removes_a_running_export(
    tracker: ExperimentTracker,
    store: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fcntl

    built, resume = threading.Event(), threading.Event()
    artifact = tmp_path / "exp.tar"
    exporter = threading.Thread(
        target=tracker.export, args=(str(artifact),), kwargs={"experiment_id": EXP_ID}
    )
    parent_locks: set[int] = set()
    build = _snapshot._build_snapshot

    def paused_build(*args: Any) -> _snapshot.ExperimentSnapshot:  # noqa: ANN401
        snapshot = build(*args)
        built.set()
        resume.wait(FORK_TIMEOUT)
        return snapshot

    def child() -> bool:
        if _snapshot._held_work_dir_locks or any(map(_is_open, parent_locks)):
            return False
        (work_dir,) = _work_dirs(store)
        fd = os.open(work_dir / _snapshot.WORK_DIR_LOCK, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            pass
        finally:
            os.close(fd)
        two_days_ago = time.time() - 2 * 24 * 3600
        os.utime(work_dir, (two_days_ago, two_days_ago))
        monkeypatch.setattr(_snapshot, "_process_exists", lambda pid: False)
        _snapshot.remove_abandoned_work_dirs(store / EXP_ID)
        return work_dir.exists()

    monkeypatch.setattr(_snapshot, "_build_snapshot", paused_build)
    exporter.start()
    assert built.wait(30)
    parent_locks.update(_snapshot._held_work_dir_locks)
    exit_code = _fork(child)
    resume.set()
    exporter.join(FORK_TIMEOUT)

    assert len(parent_locks) == 1
    assert exit_code == 0
    assert not exporter.is_alive()
    assert ExperimentReference(str(artifact)).validate()
    assert _work_dirs(store) == []
    assert _snapshot._held_work_dir_locks == set()
