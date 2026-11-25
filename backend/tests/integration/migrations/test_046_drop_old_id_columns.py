from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.alembic import run_alembic

TABLES = (
    "artifacts",
    "bucket_secrets",
    "collections",
    "deployments",
    "orbit_members",
    "orbit_secrets",
    "orbits",
    "organization_invites",
    "organization_members",
    "organizations",
    "satellite_queue",
    "satellites",
    "stats_emails",
    "token_black_list",
    "users",
)


def _tables_with_old_id(connection: Connection) -> set[str]:
    inspector = inspect(connection)
    return {
        table
        for table in TABLES
        if "old_id" in {column["name"] for column in inspector.get_columns(table)}
    }


class TestDropOldIdColumnsMigration:
    async def test_upgrade_drops_and_downgrade_restores_old_id(
        self, engine: AsyncEngine
    ) -> None:
        for upgrade in (False, True):
            await run_alembic(
                engine,
                "upgrade" if upgrade else "downgrade",
                "head" if upgrade else "045",
            )
            async with engine.connect() as connection:
                remaining = await connection.run_sync(_tables_with_old_id)
            assert remaining == (set() if upgrade else set(TABLES))
