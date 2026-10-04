from typing import Literal

from alembic import command
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from utils.db import cfg as alembic_cfg


async def run_alembic(
    engine: AsyncEngine, action: Literal["upgrade", "downgrade"], revision: str
) -> None:
    def run(connection: Connection) -> None:
        alembic_cfg.attributes["connection"] = connection
        getattr(command, action)(alembic_cfg, revision)

    async with engine.begin() as connection:
        await connection.run_sync(run)
