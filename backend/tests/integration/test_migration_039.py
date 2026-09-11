"""Migration 039 repairs deployment JSONB columns that hold JSON null."""

import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine
from utils.db import cfg

from tests.conftest import SatelliteFixtureData

BROKEN_COLUMN = "dynamic_attributes_secrets"
CONSTRAINT = f"deployments_{BROKEN_COLUMN}_is_object_check"


def _alembic_step(revision: str, upgrade: bool) -> Callable[[Connection], None]:
    def run(connection: Connection) -> None:
        config: Config = cfg
        config.attributes["connection"] = connection
        if upgrade:
            command.upgrade(config, revision)
        else:
            command.downgrade(config, revision)

    return run


async def _migrate(engine: AsyncEngine, revision: str, *, upgrade: bool) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_alembic_step(revision, upgrade))


async def _set_raw(engine: AsyncEngine, deployment_id: uuid.UUID, value: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                f"UPDATE deployments SET {BROKEN_COLUMN} = CAST(:value AS jsonb) "  # noqa: S608
                "WHERE id = :id"
            ),
            {"value": value, "id": deployment_id},
        )


async def _read_raw(engine: AsyncEngine, deployment_id: uuid.UUID) -> str:
    async with engine.connect() as conn:
        return str(
            (
                await conn.execute(
                    sa.text(
                        f"SELECT {BROKEN_COLUMN}::text FROM deployments "  # noqa: S608
                        "WHERE id = :id"
                    ),
                    {"id": deployment_id},
                )
            ).scalar_one()
        )


@pytest_asyncio.fixture
async def deployment_at_038(
    create_satellite: SatelliteFixtureData,
) -> AsyncGenerator[tuple[AsyncEngine, uuid.UUID]]:
    """A deployment on a schema rolled back to 038, so 039 can be re-run."""
    data = create_satellite
    created, _ = await DeploymentRepository(data.engine).create_deployment(
        DeploymentCreate(
            name="to-repair",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
        )
    )
    await _migrate(data.engine, "038", upgrade=False)
    yield data.engine, created.id
    await _migrate(data.engine, "039", upgrade=True)


@pytest.mark.asyncio
async def test_upgrade_replaces_json_null_with_an_empty_object(
    deployment_at_038: tuple[AsyncEngine, uuid.UUID],
) -> None:
    engine, deployment_id = deployment_at_038
    await _set_raw(engine, deployment_id, "null")

    await _migrate(engine, "039", upgrade=True)

    assert await _read_raw(engine, deployment_id) == "{}"


@pytest.mark.asyncio
async def test_upgrade_leaves_populated_objects_alone(
    deployment_at_038: tuple[AsyncEngine, uuid.UUID],
) -> None:
    engine, deployment_id = deployment_at_038
    await _set_raw(engine, deployment_id, '{"token": "abc"}')

    await _migrate(engine, "039", upgrade=True)

    assert await _read_raw(engine, deployment_id) == '{"token": "abc"}'


@pytest.mark.asyncio
async def test_upgrade_refuses_to_discard_other_shapes(
    deployment_at_038: tuple[AsyncEngine, uuid.UUID],
) -> None:
    """An array is not something this bug produced, so it must not be erased."""
    engine, deployment_id = deployment_at_038
    await _set_raw(engine, deployment_id, '["recoverable"]')

    with pytest.raises(RuntimeError, match="non-object values"):
        await _migrate(engine, "039", upgrade=True)

    assert await _read_raw(engine, deployment_id) == '["recoverable"]'
    await _set_raw(engine, deployment_id, "{}")


@pytest.mark.asyncio
async def test_upgrade_constrains_the_column_to_objects(
    deployment_at_038: tuple[AsyncEngine, uuid.UUID],
) -> None:
    engine, deployment_id = deployment_at_038

    await _migrate(engine, "039", upgrade=True)

    with pytest.raises(sa.exc.IntegrityError, match=CONSTRAINT):
        await _set_raw(engine, deployment_id, "null")
