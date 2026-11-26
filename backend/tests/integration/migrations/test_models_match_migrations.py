import importlib
import pkgutil
import re

import luml.models
from alembic import command
from luml.models import Base
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from utils.db import cfg as alembic_cfg

MIGRATED_SCHEMA = "public"
MODELS_SCHEMA = "from_models"

COLUMNS = text(
    """
    SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod),
           a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
    WHERE n.nspname = :schema AND c.relkind = 'r'
      AND a.attnum > 0 AND NOT a.attisdropped
      AND c.relname <> 'alembic_version'
    """
)
CONSTRAINTS = text(
    """
    SELECT c.relname, con.contype, pg_get_constraintdef(con.oid)
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = :schema AND c.relname <> 'alembic_version'
    """
)
INDEXES = text(
    """
    SELECT tablename, indexdef FROM pg_indexes
    WHERE schemaname = :schema AND tablename <> 'alembic_version'
    """
)
INDEX_NAME_AND_TABLE = re.compile(r"^CREATE (UNIQUE )?INDEX \S+ ON \S+ ")

Catalog = dict[str, set[tuple[object, ...]]]


def _catalog(connection: Connection, schema: str) -> Catalog:
    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
    params = {"schema": schema}
    return {
        "columns": {tuple(row) for row in connection.execute(COLUMNS, params)},
        "constraints": {tuple(row) for row in connection.execute(CONSTRAINTS, params)},
        "indexes": {
            (table, INDEX_NAME_AND_TABLE.sub(r"\1", definition))
            for table, definition in connection.execute(INDEXES, params)
        },
    }


def _migrated_and_models_catalogs(connection: Connection) -> tuple[Catalog, Catalog]:
    for module in pkgutil.iter_modules(luml.models.__path__):
        importlib.import_module(f"{luml.models.__name__}.{module.name}")
    connection.execute(text(f'CREATE SCHEMA "{MODELS_SCHEMA}"'))
    Base.metadata.create_all(
        connection.execution_options(schema_translate_map={None: MODELS_SCHEMA})
    )
    return (
        _catalog(connection, MIGRATED_SCHEMA),
        _catalog(connection, MODELS_SCHEMA),
    )


class TestModelsMatchMigrations:
    async def test_autogenerate_finds_no_difference_at_head(
        self, engine: AsyncEngine
    ) -> None:
        def check(connection: Connection) -> None:
            alembic_cfg.attributes["connection"] = connection
            command.check(alembic_cfg)

        async with engine.connect() as connection:
            await connection.run_sync(check)

    async def test_catalog_at_head_matches_tables_created_from_models(
        self, engine: AsyncEngine
    ) -> None:
        async with engine.connect() as connection:
            migrated, models = await connection.run_sync(_migrated_and_models_catalogs)

        for kind in migrated:
            assert migrated[kind] == models[kind], kind
