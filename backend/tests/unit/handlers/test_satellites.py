import datetime
import uuid
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from dataforce_studio.handlers.satellites import SatelliteHandler
from dataforce_studio.infra.exceptions import ApplicationError, NotFoundError
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.schemas.satellite import (
    Satellite,
    SatelliteCapability,
    SatelliteCreateIn,
    SatelliteCreateOut,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

handler = SatelliteHandler()


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites(
    mock_check_orbit_action_access: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 123
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "test"}
    }

    expected = [
        Satellite(
            id=1,
            orbit_id=orbit_id,
            name="test",
            base_url="https://url.com",
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
    ]
    mock_list_satellites.return_value = expected

    result = await handler.list_satellites(user_id, organization_id, orbit_id)

    assert result == expected
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.SATELLITE, Action.LIST
    )
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 123
    satellite_id = 456

    expected = Satellite(
        id=1,
        orbit_id=orbit_id,
        name="test",
        base_url="https://url.com",
        paired=False,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )
    mock_get_satellite.return_value = expected

    result = await handler.get_satellite(
        user_id, organization_id, orbit_id, satellite_id
    )

    assert result == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.SATELLITE, Action.READ
    )


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 123
    satellite_id = 456

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.get_satellite(user_id, organization_id, orbit_id, satellite_id)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.SATELLITE, Action.READ
    )


@patch(
    "dataforce_studio.handlers.satellites.SatelliteHandler._get_key_hash",
)
@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.create_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_create_satellite: AsyncMock,
    mock_get_key_hash: Mock,
) -> None:
    user_id = 1
    user_name = "John Doe"
    organization_id = 1
    orbit_id = 123

    payload = {"created_by_user": user_name}
    satellite_create_in = SatelliteCreateIn(name="test-satellite")
    mock_satellite = Satellite(
        id=1,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url="https://url.com",
        paired=False,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )
    mock_task = SatelliteQueueTask(
        id=1,
        satellite_id=mock_satellite.id,
        orbit_id=orbit_id,
        type=SatelliteTaskType.PAIRING,
        payload=payload,
        status=SatelliteTaskStatus.PENDING,
        scheduled_at=datetime.datetime.now(),
        started_at=datetime.datetime.now(),
        finished_at=None,
        result=None,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_public_user.return_value = Mock(full_name=user_name)
    mock_create_satellite.return_value = mock_satellite, mock_task
    mock_get_key_hash.return_value = str(uuid.uuid4())

    result = await handler.create_satellite(
        user_id, organization_id, orbit_id, satellite_create_in
    )

    assert isinstance(result, SatelliteCreateOut)
    assert result.satellite == mock_satellite
    assert result.task == mock_task
    assert result.task.payload == payload
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_public_user.assert_awaited_once_with(user_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.SATELLITE, Action.CREATE
    )


@patch(
    "dataforce_studio.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_orbit_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 123

    satellite_create_in = SatelliteCreateIn(name="test-satellite")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, satellite_create_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.SATELLITE, Action.CREATE
    )


@patch(
    "dataforce_studio.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.PermissionsHandler.check_orbit_action_access",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_user_not_found(
    mock_check_orbit_action_access: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_public_user: AsyncMock,
) -> None:
    user_id = 1
    organization_id = 1
    orbit_id = 123

    satellite_create_in = SatelliteCreateIn(name="test-satellite")

    mock_get_orbit_simple.return_value = Mock()
    mock_get_public_user.return_value = None

    with pytest.raises(NotFoundError, match="User not found") as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, satellite_create_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_public_user.assert_awaited_once_with(user_id)
    mock_check_orbit_action_access.assert_awaited_once_with(
        organization_id, orbit_id, user_id, Resource.SATELLITE, Action.CREATE
    )


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = 1
    satellite_id = 123
    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    unpaired_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url=None,
        paired=False,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )
    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url=base_url,
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=datetime.datetime.now(),
    )

    mock_get_satellite.return_value = unpaired_satellite
    mock_pair_satellite.return_value = expected

    satellite = await handler.pair_satellite(satellite_id, base_url, capabilities)

    assert satellite == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_awaited_once_with(satellite_id, base_url, capabilities)


@pytest.mark.asyncio
async def test_pair_satellite_empty_capabilities() -> None:
    satellite_id = 123
    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {}

    with pytest.raises(ApplicationError, match="Invalid capabilities") as error:
        await handler.pair_satellite(satellite_id, base_url, capabilities)

    assert error.value.status_code == 400


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_satellite_not_found(
    mock_get_satellite: AsyncMock,
) -> None:
    satellite_id = 123
    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.pair_satellite(satellite_id, base_url, capabilities)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_capabilities_error(
    mock_get_satellite: AsyncMock,
) -> None:
    orbit_id = 1
    satellite_id = 123
    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: None
    }
    initial_capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "test"}
    }

    initial_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url=None,
        paired=True,
        capabilities=initial_capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = initial_satellite

    with pytest.raises(ApplicationError, match="Satellite already paired") as error:
        await handler.pair_satellite(satellite_id, base_url, capabilities)

    assert error.value.status_code == 409
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_already_paired(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = 1
    satellite_id = 123
    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url=base_url,
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=datetime.datetime.now(),
    )

    mock_get_satellite.return_value = expected

    satellite = await handler.pair_satellite(satellite_id, base_url, capabilities)

    assert satellite == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_not_awaited()


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_update_error(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = 1
    satellite_id = 123
    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    unpaired_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url=None,
        paired=False,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = unpaired_satellite
    mock_pair_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.pair_satellite(satellite_id, base_url, capabilities)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_awaited_once_with(satellite_id, base_url, capabilities)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.touch_last_seen",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_touch_last_seen(mock_touch_last_seen: AsyncMock) -> None:
    satellite_id = 123

    await handler.touch_last_seen(satellite_id)

    mock_touch_last_seen.assert_awaited_once_with(satellite_id)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.list_tasks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tasks(mock_list_tasks: AsyncMock) -> None:
    satellite_id = 123

    expected = [
        SatelliteQueueTask(
            id=1,
            satellite_id=satellite_id,
            orbit_id=1,
            type=SatelliteTaskType.PAIRING,
            payload={"created_by_user": "Full Name"},
            status=SatelliteTaskStatus.PENDING,
            scheduled_at=datetime.datetime.now(),
            started_at=datetime.datetime.now(),
            finished_at=None,
            result=None,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    ]

    mock_list_tasks.return_value = expected

    tasks = await handler.list_tasks(satellite_id)

    assert tasks == expected
    mock_list_tasks.assert_awaited_once_with(satellite_id, None)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.list_tasks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tasks_with_status(mock_list_tasks: AsyncMock) -> None:
    satellite_id = 123
    status = SatelliteTaskStatus.PENDING

    expected = [Mock(status=status), Mock(status=status)]

    mock_list_tasks.return_value = expected

    tasks = await handler.list_tasks(satellite_id, status)

    assert tasks == expected
    assert tasks[0].status == status
    mock_list_tasks.assert_awaited_once_with(satellite_id, status)


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.update_task_status",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_task_status_success(mock_update_task_status: AsyncMock) -> None:
    satellite_id = 123
    task_id = 456
    status = SatelliteTaskStatus.DONE
    result = {"success": True}

    expected = SatelliteQueueTask(
        id=1,
        satellite_id=satellite_id,
        orbit_id=1,
        type=SatelliteTaskType.PAIRING,
        payload={"created_by_user": "Full Name"},
        status=status,
        scheduled_at=datetime.datetime.now(),
        started_at=datetime.datetime.now(),
        finished_at=datetime.datetime.now(),
        result=result,
        created_at=datetime.datetime.now(),
        updated_at=None,
    )
    mock_update_task_status.return_value = expected

    task = await handler.update_task_status(satellite_id, task_id, status, result)

    assert task == expected
    assert expected.status == status
    assert expected.finished_at
    assert expected.result == result
    mock_update_task_status.assert_awaited_once_with(
        satellite_id, task_id, status, result
    )


@patch(
    "dataforce_studio.handlers.satellites.SatelliteRepository.update_task_status",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_task_status_not_found(mock_update_task_status: AsyncMock) -> None:
    satellite_id = 123
    task_id = 456
    status = SatelliteTaskStatus.DONE

    mock_update_task_status.return_value = None

    with pytest.raises(NotFoundError, match="Task not found") as error:
        await handler.update_task_status(satellite_id, task_id, status)

    assert error.value.status_code == 404
    mock_update_task_status.assert_awaited_once_with(
        satellite_id, task_id, status, None
    )
