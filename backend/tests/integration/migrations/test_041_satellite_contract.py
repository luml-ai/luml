import re

import pytest
from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentUpdate
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.alembic import run_alembic
from tests.support.seeds import SatelliteFixtureData


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


class TestSatelliteContractMigration:
    async def test_upgrade_and_downgrade_toggle_satellite_contract_schema(
        self, engine: AsyncEngine
    ) -> None:
        await run_alembic(engine, "downgrade", "040")
        assert "provider_ref" not in await _columns(engine, "deployments")
        assert "progress_note" not in await _columns(engine, "deployments")
        assert "kit_info" not in await _columns(engine, "satellites")
        assert await _has_inference_url_unique_constraint(engine)

        await run_alembic(engine, "upgrade", "head")
        assert {"provider_ref", "progress_note"}.issubset(
            await _columns(engine, "deployments")
        )
        assert "kit_info" in await _columns(engine, "satellites")
        assert not await _has_inference_url_unique_constraint(engine)

        await run_alembic(engine, "downgrade", "040")
        assert "provider_ref" not in await _columns(engine, "deployments")
        assert "progress_note" not in await _columns(engine, "deployments")
        assert "kit_info" not in await _columns(engine, "satellites")
        assert await _has_inference_url_unique_constraint(engine)

    async def test_downgrade_raises_naming_inference_url_when_duplicates_exist(
        self, engine: AsyncEngine, seeded_satellite: SatelliteFixtureData
    ) -> None:
        repository = DeploymentRepository(engine)
        deployments = [
            (
                await repository.create_deployment(
                    DeploymentCreate(
                        name=f"duplicate-address-{index}",
                        orbit_id=seeded_satellite.orbit.id,
                        satellite_id=seeded_satellite.satellite.id,
                        artifact_id=seeded_satellite.model.id,
                    )
                )
            )[0]
            for index in range(2)
        ]
        inference_url = "https://shared.example/models"
        for deployment in deployments:
            await repository.update_deployment(
                deployment.id,
                seeded_satellite.satellite.id,
                DeploymentUpdate(id=deployment.id, inference_url=inference_url),
            )

        with pytest.raises(RuntimeError, match=re.escape(inference_url)):
            await run_alembic(engine, "downgrade", "040")

        assert {"provider_ref", "progress_note"}.issubset(
            await _columns(engine, "deployments")
        )
