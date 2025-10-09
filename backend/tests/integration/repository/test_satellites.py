import uuid
from typing import Any

import pytest
import uuid6
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.satellites import SatelliteRepository
from dataforce_studio.schemas.satellite import (
    SatelliteCapability,
    SatelliteCreate,
    SatelliteTaskStatus,
    SatelliteTaskType,
)
from tests.conftest import OrbitFixtureData


@pytest.mark.asyncio
async def test_create_satellite(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)

    assert satellite
    assert satellite.orbit_id == orbit.id
    assert task
    assert task.satellite_id == satellite.id
    assert task.orbit_id == orbit.id
    assert task.type == SatelliteTaskType.PAIRING
    assert task.status == "pending"


@pytest.mark.asyncio
async def test_get_satellite(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)

    fetched_satellite = await repo.get_satellite(satellite.id)

    assert fetched_satellite
    assert fetched_satellite.id == satellite.id


@pytest.mark.asyncio
async def test_get_satellite_not_found(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = SatelliteRepository(engine)

    fetched_satellite = await repo.get_satellite(uuid6.uuid7())

    assert fetched_satellite is None


@pytest.mark.asyncio
async def test_get_satellite_get_satellite_by_hash(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)

    fetched_satellite = await repo.get_satellite_by_hash(satellite_data.api_key_hash)

    assert fetched_satellite
    assert fetched_satellite.id == satellite.id


@pytest.mark.asyncio
async def test_list_satellites(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)

    fetched_satellites = await repo.list_satellites(orbit.id)

    assert len(fetched_satellites) == 1
    assert fetched_satellites[0].id == satellite.id


@pytest.mark.asyncio
async def test_pair_satellite(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)

    base_url = "https://test-satellite.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"config": "value"}
    }

    paired_satellite = await repo.pair_satellite(satellite.id, base_url, capabilities)

    assert paired_satellite
    assert paired_satellite.id == satellite.id
    assert paired_satellite.paired is True
    assert paired_satellite.base_url == base_url
    assert paired_satellite.capabilities == capabilities


@pytest.mark.asyncio
async def test_list_tasks(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)
    all_tasks = await repo.list_tasks(satellite.id)

    assert len(all_tasks) == 1
    assert all_tasks[0].id == task.id
    assert all_tasks[0].satellite_id == satellite.id
    assert all_tasks[0].type == SatelliteTaskType.PAIRING
    assert all_tasks[0].status == SatelliteTaskStatus.PENDING


@pytest.mark.asyncio
async def test_list_tasks_with_status(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)
    pending_tasks = await repo.list_tasks(satellite.id, SatelliteTaskStatus.PENDING)

    assert len(pending_tasks) == 1


@pytest.mark.asyncio
async def test_list_tasks_empty(create_database_and_apply_migrations: str) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = SatelliteRepository(engine)

    tasks = await repo.list_tasks(uuid6.uuid7())

    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_update_task_status(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = SatelliteRepository(engine)

    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, initial_task = await repo.create_satellite(satellite_data)

    updated_task = await repo.update_task_status(
        satellite.id, initial_task.id, SatelliteTaskStatus.DONE, {"status": 200}
    )

    assert updated_task
    assert updated_task.id == initial_task.id
    assert updated_task.status == SatelliteTaskStatus.DONE


@pytest.mark.asyncio
async def test_touch_last_seen(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit

    repo = SatelliteRepository(engine)
    satellite_data = SatelliteCreate(
        orbit_id=orbit.id, api_key_hash=str(uuid.uuid4()), name="test"
    )
    satellite, task = await repo.create_satellite(satellite_data)

    original_last_seen = satellite.last_seen_at
    assert original_last_seen is None

    await repo.touch_last_seen(satellite.id)
    seen_satellite = await repo.get_satellite(satellite.id)

    assert seen_satellite
    assert seen_satellite.last_seen_at is not None
    assert seen_satellite.last_seen_at != original_last_seen
