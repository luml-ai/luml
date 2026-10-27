import os
from pathlib import Path

import pytest

from luml.experiments.backends.sqlite import ConnectionPool


def _get_windows_db_path(tmp_path: Path, exp_name: str) -> str:
    if os.name == "nt":
        db_path = tmp_path / "store" / "experiments" / exp_name / "exp.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return str(db_path)
    return rf"C:\store\experiments\{exp_name}\exp.db"


class TestConnectionPool:
    def test_mark_experiment_inactive_closes_windows_style_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        windows_exp_db = _get_windows_db_path(tmp_path, "exp-1")
        pool = ConnectionPool()
        with pool.get_connection(windows_exp_db):
            pass

        pool.mark_experiment_inactive("exp-1")

        assert windows_exp_db not in pool._connections

    def test_evict_prefers_inactive_windows_style_experiment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        windows_exp_db = _get_windows_db_path(tmp_path, "exp-1")
        pool = ConnectionPool(max_connections=2)
        pool.mark_experiment_active("exp-1")
        with pool.get_connection(windows_exp_db):
            pass
        inactive_db = _get_windows_db_path(tmp_path, "exp-2")
        with pool.get_connection(inactive_db):
            pass

        with pool.get_connection(_get_windows_db_path(tmp_path, "exp-3")):
            pass

        assert windows_exp_db in pool._connections
        assert inactive_db not in pool._connections
        pool.close_all()
