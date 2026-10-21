from pathlib import Path

import pytest

from luml.experiments.backends.sqlite import ConnectionPool

WINDOWS_EXP_DB = r"C:\store\experiments\exp-1\exp.db"


class TestConnectionPool:
    def test_mark_experiment_inactive_closes_windows_style_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        pool = ConnectionPool()
        with pool.get_connection(WINDOWS_EXP_DB):
            pass

        pool.mark_experiment_inactive("exp-1")

        assert WINDOWS_EXP_DB not in pool._connections

    def test_evict_prefers_inactive_windows_style_experiment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        pool = ConnectionPool(max_connections=2)
        pool.mark_experiment_active("exp-1")
        with pool.get_connection(WINDOWS_EXP_DB):
            pass
        inactive_db = r"C:\store\experiments\exp-2\exp.db"
        with pool.get_connection(inactive_db):
            pass

        with pool.get_connection(r"C:\store\experiments\exp-3\exp.db"):
            pass

        assert WINDOWS_EXP_DB in pool._connections
        assert inactive_db not in pool._connections
        pool.close_all()
