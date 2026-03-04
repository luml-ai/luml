import logging
from importlib import resources

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

logger = logging.getLogger(__name__)


def run_migrations(engine: Engine) -> None:
    migrations_path = str(
        resources.files("luml_agent") / "migrations"
    )
    cfg = Config()
    cfg.set_main_option("script_location", migrations_path)
    cfg.set_main_option("sqlalchemy.url", str(engine.url))

    logger.info("Running migrations from %s", migrations_path)
    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
    logger.info("Migrations complete")
