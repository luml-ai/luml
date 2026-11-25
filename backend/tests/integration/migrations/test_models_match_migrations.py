from alembic import command
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from utils.db import cfg as alembic_cfg


class TestModelsMatchMigrations:
    async def test_autogenerate_finds_no_difference_at_head(
        self, engine: AsyncEngine
    ) -> None:
        def check(connection: Connection) -> None:
            alembic_cfg.attributes["connection"] = connection
            command.check(alembic_cfg)

        async with engine.connect() as connection:
            await connection.run_sync(check)
