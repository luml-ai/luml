import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from luml.experiments.backends.migration_runner import ExperimentMigrationRunner
from luml.experiments.backends.sqlite import ConnectionPool, SQLiteBackend


def test_concurrent_static_and_dynamic_writes(
    backend_with_experiment: tuple[SQLiteBackend, str],
) -> None:
    backend, experiment_id = backend_with_experiment
    barrier = threading.Barrier(8)

    def log(worker: int) -> None:
        barrier.wait()
        for step in range(300):
            backend.log_dynamic(experiment_id, "metric", worker * 300 + step)
            backend.log_static(experiment_id, f"worker-{worker}-{step}", step)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(log, range(8)))

    data = backend.get_experiment_data(experiment_id)
    metrics = data.dynamic_metrics["metric"]
    assert len(metrics) == 2400
    assert {metric["step"] for metric in metrics} == set(range(2400))
    assert {metric["value"] for metric in metrics} == set(range(2400))
    assert len(data.static_params) == 2400


def test_concurrent_meta_writes(backend: SQLiteBackend) -> None:
    barrier = threading.Barrier(8)

    def initialize(worker: int) -> None:
        barrier.wait()
        for step in range(10):
            backend.initialize_experiment(f"worker-{worker}-{step}", group="shared")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(initialize, range(8)))

    assert len(backend.list_experiments()) == 80
    assert len(backend.list_groups()) == 1


def test_concurrent_metadata_updates_preserve_all_keys(
    backend_with_experiment: tuple[SQLiteBackend, str],
) -> None:
    backend, experiment_id = backend_with_experiment
    barrier = threading.Barrier(8)

    def update(worker: int) -> None:
        barrier.wait()
        for step in range(30):
            backend.update_experiment_metadata(
                experiment_id, {f"worker-{worker}-{step}": step}
            )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(update, range(8)))

    assert backend.get_experiment_metadata(experiment_id) == {
        f"worker-{worker}-{step}": step for worker in range(8) for step in range(30)
    }


def test_concurrent_lazy_migration_runs_once(
    backend_with_experiment: tuple[SQLiteBackend, str],
) -> None:
    backend, experiment_id = backend_with_experiment
    backend._migrated_experiment_dbs.clear()
    barrier = threading.Barrier(8)
    migrate = ExperimentMigrationRunner.migrate

    def initialize(_: int) -> None:
        barrier.wait()
        backend._ensure_experiment_initialized(experiment_id)

    with (
        patch.object(ExperimentMigrationRunner, "migrate", autospec=True) as migration,
        ThreadPoolExecutor(max_workers=8) as executor,
    ):
        migration.side_effect = migrate
        list(executor.map(initialize, range(8)))

    assert migration.call_count == 1


def test_checked_out_connection_survives_eviction(tmp_path: Path) -> None:
    pool = ConnectionPool(max_connections=2)
    with pool.get_connection(tmp_path / "held.db") as held:
        for index in range(12):
            with pool.get_connection(tmp_path / f"other-{index}.db") as other:
                assert other.execute("SELECT 1").fetchone() == (1,)
        assert held.execute("SELECT 1").fetchone() == (1,)
    pool.close_all()


@pytest.mark.parametrize("close", ["inactive", "connection", "all"])
def test_close_waits_for_last_checkout(tmp_path: Path, close: str) -> None:
    experiment_id = "held"
    db_path = tmp_path / experiment_id / "exp.db"
    db_path.parent.mkdir()
    pool = ConnectionPool()
    pool.mark_experiment_active(experiment_id)
    with pool.get_connection(db_path) as outer:
        with pool.get_connection(db_path) as inner:
            assert inner is outer
            if close == "inactive":
                pool.mark_experiment_inactive(experiment_id)
            elif close == "connection":
                pool.close_connection(str(db_path))
            else:
                pool.close_all()
            assert inner.execute("SELECT 1").fetchone() == (1,)
        assert outer.execute("SELECT 1").fetchone() == (1,)
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        outer.execute("SELECT 1")
    with pool.get_connection(db_path) as reopened:
        assert reopened is not outer
        assert reopened.execute("SELECT 1").fetchone() == (1,)
    pool.close_all()


def test_checkout_released_after_error(tmp_path: Path) -> None:
    pool = ConnectionPool()
    db_path = tmp_path / "exp.db"
    with (
        pytest.raises(ValueError, match="interrupted"),
        pool.get_connection(db_path) as conn,
    ):
        raise ValueError("interrupted")
    pool.close_all()
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")


def test_failed_write_does_not_leak_transaction(tmp_path: Path) -> None:
    pool = ConnectionPool()
    db_path = tmp_path / "exp.db"
    with pool.get_connection(db_path, write=True) as conn:
        conn.execute("CREATE TABLE items (value INTEGER UNIQUE)")
        conn.commit()
    with (
        pytest.raises(sqlite3.IntegrityError),
        pool.get_connection(db_path, write=True) as conn,
    ):
        conn.executescript(
            "BEGIN; INSERT INTO items VALUES (1); INSERT INTO items VALUES (1)"
        )
    with pool.get_connection(db_path, write=True) as conn:
        conn.execute("INSERT INTO items VALUES (2)")
        conn.commit()
        assert conn.execute("SELECT value FROM items").fetchall() == [(2,)]
    pool.close_all()


def test_active_connection_is_not_evicted(tmp_path: Path) -> None:
    db_path = tmp_path / "active" / "exp.db"
    db_path.parent.mkdir()
    pool = ConnectionPool(max_connections=1)
    pool.mark_experiment_active("active")
    with pool.get_connection(db_path) as active:
        assert active.execute("SELECT 1").fetchone() == (1,)
    with pool.get_connection(tmp_path / "other.db"):
        pass
    with pool.get_connection(db_path) as still_active:
        assert still_active is active
    pool.close_all()


def test_end_experiment_keeps_checked_out_connection_alive(
    backend_with_experiment: tuple[SQLiteBackend, str],
) -> None:
    backend, experiment_id = backend_with_experiment
    with backend._get_experiment_connection(experiment_id) as conn:
        backend.end_experiment(experiment_id)
        assert conn.execute("SELECT COUNT(*) FROM dynamic_metrics").fetchone() == (0,)
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")
