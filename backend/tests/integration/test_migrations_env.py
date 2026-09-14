import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]


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
    @pytest.mark.asyncio
    async def test_cli_uses_exported_dsn(
        self, create_database_and_apply_migrations: str
    ) -> None:
        result = _alembic_current(create_database_and_apply_migrations)

        assert result.returncode == 0, result.stderr
        assert "(head)" in result.stdout

    def test_cli_fails_on_unparseable_exported_dsn(self) -> None:
        result = _alembic_current("not-a-dsn")

        assert result.returncode != 0
        assert "Could not parse SQLAlchemy URL" in result.stderr
