import re

import pytest
from alembic import command
from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentUpdate
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from utils.db import cfg as alembic_cfg

from tests.conftest import SatelliteFixtureData


async def _migrate(engine: AsyncEngine, revision: str, *, upgrade: bool) -> None:
    def run(connection: Connection) -> None:
        alembic_cfg.attributes["connection"] = connection
        if upgrade:
            command.upgrade(alembic_cfg, revision)
        else:
            command.downgrade(alembic_cfg, revision)

    async with engine.begin() as connection:
        await connection.run_sync(run)


async def _columns(engine: AsyncEngine, table: str) -> set[str]:
    def load(connection: Connection) -> set[str]:
        return {
            str(column["name"]) for column in inspect(connection).get_columns(table)
        }

    async with engine.connect() as connection:
        return await connection.run_sync(load)


async def _has_inference_url_unique_constraint(engine: AsyncEngine) -> bool:
    def load(connection: Connection) -> bool:
        constraints = inspect(connection).get_unique_constraints("deployments")
        return any(
            constraint["column_names"] == ["inference_url"]
            for constraint in constraints
        )

    async with engine.connect() as connection:
        return await connection.run_sync(load)


@pytest.mark.asyncio
async def test_migration_upgrades_and_downgrades(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    try:
        await _migrate(engine, "040", upgrade=False)
        assert "provider_ref" not in await _columns(engine, "deployments")
        assert "progress_note" not in await _columns(engine, "deployments")
        assert "kit_info" not in await _columns(engine, "satellites")
        assert await _has_inference_url_unique_constraint(engine)

        await _migrate(engine, "head", upgrade=True)
        assert {"provider_ref", "progress_note"}.issubset(
            await _columns(engine, "deployments")
        )
        assert "kit_info" in await _columns(engine, "satellites")
        assert not await _has_inference_url_unique_constraint(engine)

        await _migrate(engine, "040", upgrade=False)
        assert "provider_ref" not in await _columns(engine, "deployments")
        assert "progress_note" not in await _columns(engine, "deployments")
        assert "kit_info" not in await _columns(engine, "satellites")
        assert await _has_inference_url_unique_constraint(engine)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_names_duplicate_inference_urls(
    create_satellite: SatelliteFixtureData,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    deployments = [
        (
            await repo.create_deployment(
                DeploymentCreate(
                    name=f"duplicate-address-{index}",
                    orbit_id=data.orbit.id,
                    satellite_id=data.satellite.id,
                    artifact_id=data.model.id,
                )
            )
        )[0]
        for index in range(2)
    ]
    inference_url = "https://shared.example/models"
    for deployment in deployments:
        await repo.update_deployment(
            deployment.id,
            data.satellite.id,
            DeploymentUpdate(id=deployment.id, inference_url=inference_url),
        )

    with pytest.raises(RuntimeError, match=re.escape(inference_url)):
        await _migrate(data.engine, "040", upgrade=False)

    assert {"provider_ref", "progress_note"}.issubset(
        await _columns(data.engine, "deployments")
    )
