from importlib import resources
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from luml_agent.migrate import run_migrations
from luml_agent.orm import create_db_engine


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


class TestRunMigrations:
    def test_creates_all_tables(self, tmp_db_path: Path) -> None:
        engine = create_db_engine(f"sqlite:///{tmp_db_path}")
        run_migrations(engine)

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "repositories",
            "tasks",
            "runs",
            "run_nodes",
            "run_edges",
            "run_events",
            "node_sessions",
            "alembic_version",
        }
        assert expected <= tables

        engine.dispose()

    def test_stamps_alembic_version(self, tmp_db_path: Path) -> None:
        engine = create_db_engine(f"sqlite:///{tmp_db_path}")
        run_migrations(engine)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchone()
            assert row is not None
            assert row[0] == "b3d5e7f9a124"

        engine.dispose()

    def test_idempotent(self, tmp_db_path: Path) -> None:
        engine = create_db_engine(f"sqlite:///{tmp_db_path}")
        run_migrations(engine)
        run_migrations(engine)

        inspector = inspect(engine)
        assert "repositories" in inspector.get_table_names()

        engine.dispose()


class TestMigrationFilesDiscoverable:
    def test_env_py_exists(self) -> None:
        migrations = resources.files("luml_agent") / "migrations"
        env_py = migrations / "env.py"
        assert resources.as_file(env_py)

    def test_versions_dir_exists(self) -> None:
        migrations = resources.files("luml_agent") / "migrations"
        versions = migrations / "versions"
        assert resources.as_file(versions)

    def test_script_mako_exists(self) -> None:
        migrations = resources.files("luml_agent") / "migrations"
        mako = migrations / "script.py.mako"
        assert resources.as_file(mako)
