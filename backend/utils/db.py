import os

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "..", "alembic.ini")
MIGRATION_PATH = os.path.join(BASE_DIR, "..", "migrations")

cfg = Config(CONFIG_PATH)
cfg.set_main_option("script_location", MIGRATION_PATH)


async def migrate_db(conn_url: str) -> None:
    async_engine = create_async_engine(conn_url, echo=True)
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(__execute_upgrade)
    finally:
        await async_engine.dispose()


def __execute_upgrade(connection: Connection) -> None:
    cfg.attributes["connection"] = connection
    command.upgrade(cfg, "head")
