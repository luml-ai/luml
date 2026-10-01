import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]


def _alembic_current(dsn: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=BACKEND_DIR,
        env={**os.environ, "POSTGRESQL_DSN": dsn},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class TestMigrationsEnv:
    async def test_alembic_current_reports_head_when_dsn_exported(
        self, database_dsn: str
    ) -> None:
        result = _alembic_current(database_dsn)

        assert result.returncode == 0, result.stderr
        assert "(head)" in result.stdout

    def test_alembic_current_fails_when_exported_dsn_unparseable(self) -> None:
        result = _alembic_current("not-a-dsn")

        assert result.returncode != 0
        assert "Could not parse SQLAlchemy URL" in result.stderr
