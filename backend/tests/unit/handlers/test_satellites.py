import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from luml.handlers.satellites import SatelliteHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import (
    Satellite,
    SatelliteCapability,
    SatelliteCreateIn,
    SatelliteCreateOut,
    SatellitePairIn,
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
    SatelliteUpdateIn,
)

handler = SatelliteHandler()


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites(
    mock_check_permissions: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "test"}
    }

    expected = [
        Satellite(
            id=satellite_id,
            orbit_id=orbit_id,
            name="test",
            description=None,
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
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.LIST, orbit_id
    )
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test",
        description=None,
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
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.get_satellite(user_id, organization_id, orbit_id, satellite_id)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.READ, orbit_id
    )


@patch(
    "luml.handlers.satellites.SatelliteHandler._check_organization_satellites_limit",
)
@patch(
    "luml.handlers.satellites.SatelliteHandler._get_key_hash",
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.create_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_create_satellite: AsyncMock,
    mock_get_key_hash: Mock,
    mock_check_organization_satellites_limit: AsyncMock,
) -> None:
    user_name = "John Doe"
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_create_in = SatelliteCreateIn(name="test-satellite")
    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        base_url="https://url.com",
        paired=False,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_orbit_simple.return_value = Mock()
    mock_get_public_user.return_value = Mock(full_name=user_name)
    mock_create_satellite.return_value = mock_satellite
    mock_get_key_hash.return_value = str(uuid4())

    result = await handler.create_satellite(
        user_id, organization_id, orbit_id, satellite_create_in
    )

    assert isinstance(result, SatelliteCreateOut)
    assert result.satellite == mock_satellite
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_get_public_user.assert_awaited_once_with(user_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.CREATE, orbit_id
    )
    mock_check_organization_satellites_limit.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.satellites.SatelliteHandler._check_organization_satellites_limit",
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_orbit_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_check_organization_satellites_limit: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    satellite_create_in = SatelliteCreateIn(name="test-satellite")

    mock_get_orbit_simple.return_value = None

    with pytest.raises(NotFoundError, match="Orbit not found") as error:
        await handler.create_satellite(
            user_id, organization_id, orbit_id, satellite_create_in
        )

    assert error.value.status_code == 404
    mock_get_orbit_simple.assert_awaited_once_with(orbit_id, organization_id)
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.CREATE, orbit_id
    )
    mock_check_organization_satellites_limit.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.satellites.SatelliteHandler._check_organization_satellites_limit",
)
@patch(
    "luml.handlers.satellites.UserRepository.get_public_user_by_id",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_satellite_user_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    mock_get_public_user: AsyncMock,
    mock_check_organization_satellites_limit: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

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
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.CREATE, orbit_id
    )
    mock_check_organization_satellites_limit.assert_awaited_once_with(organization_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    unpaired_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
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
        description=None,
        base_url=base_url,
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=datetime.datetime.now(),
    )

    mock_get_satellite.return_value = unpaired_satellite
    mock_pair_satellite.return_value = expected

    satellite_pair_in = SatellitePairIn(
        base_url=base_url,
        capabilities=capabilities,
    )
    satellite = await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert satellite == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_awaited_once()


@pytest.mark.asyncio
async def test_pair_satellite_empty_capabilities() -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {}

    satellite_pair_in = SatellitePairIn(
        base_url=base_url,
        capabilities=capabilities,
    )

    with pytest.raises(ApplicationError, match="Invalid capabilities") as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 400


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_satellite_not_found(
    mock_get_satellite: AsyncMock,
) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    mock_get_satellite.return_value = None

    satellite_pair_in = SatellitePairIn(
        base_url=base_url,
        capabilities=capabilities,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_already_paired(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url=base_url,
        paired=True,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=datetime.datetime.now(),
    )

    mock_get_satellite.return_value = expected

    satellite_pair_in = SatellitePairIn(
        base_url=base_url,
        capabilities=capabilities,
    )
    satellite = await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert satellite == expected
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_not_awaited()


@patch(
    "luml.handlers.satellites.SatelliteRepository.pair_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_pair_satellite_update_error(
    mock_get_satellite: AsyncMock,
    mock_pair_satellite: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    base_url = "https://satellite.example.com"
    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "kdhfkgjhdkfghk"}
    }

    unpaired_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url=None,
        paired=False,
        capabilities=capabilities,
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = unpaired_satellite
    mock_pair_satellite.return_value = None

    satellite_pair_in = SatellitePairIn(
        base_url=base_url,
        capabilities=capabilities,
    )

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.pair_satellite(satellite_id, satellite_pair_in)

    assert error.value.status_code == 404
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_pair_satellite.assert_awaited_once()


@patch(
    "luml.handlers.satellites.SatelliteRepository.touch_last_seen",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_touch_last_seen(mock_touch_last_seen: AsyncMock) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    await handler.touch_last_seen(satellite_id)

    mock_touch_last_seen.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_tasks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tasks(mock_list_tasks: AsyncMock) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

    expected = [
        SatelliteQueueTask(
            id=task_id,
            satellite_id=satellite_id,
            orbit_id=orbit_id,
            type=SatelliteTaskType.DEPLOY,
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
    "luml.handlers.satellites.SatelliteRepository.list_tasks",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_tasks_with_status(mock_list_tasks: AsyncMock) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    status = SatelliteTaskStatus.PENDING

    expected = [Mock(status=status), Mock(status=status)]

    mock_list_tasks.return_value = expected

    tasks = await handler.list_tasks(satellite_id, status)

    assert tasks == expected
    assert tasks[0].status == status
    mock_list_tasks.assert_awaited_once_with(satellite_id, status)


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_task_status",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_task_status_success(mock_update_task_status: AsyncMock) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

    status = SatelliteTaskStatus.DONE
    result = {"success": True}

    expected = SatelliteQueueTask(
        id=task_id,
        satellite_id=satellite_id,
        orbit_id=orbit_id,
        type=SatelliteTaskType.DEPLOY,
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
    "luml.handlers.satellites.SatelliteRepository.update_task_status",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_task_status_not_found(mock_update_task_status: AsyncMock) -> None:
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")
    task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

    status = SatelliteTaskStatus.DONE

    mock_update_task_status.return_value = None

    with pytest.raises(NotFoundError, match="Task not found") as error:
        await handler.update_task_status(satellite_id, task_id, status)

    assert error.value.status_code == 404
    mock_update_task_status.assert_awaited_once_with(
        satellite_id, task_id, status, None
    )


@patch(
    "luml.handlers.satellites.SatelliteHandler._get_key_hash",
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_regenerate_satellite_api_key(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
    mock_get_key_hash: Mock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_get_key_hash.return_value = "hashed_key"

    api_key = await handler.regenerate_satellite_api_key(
        user_id, organization_id, orbit_id, satellite_id
    )

    assert api_key.startswith("dfssat_")
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_update_satellite.assert_awaited_once()


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_regenerate_satellite_api_key_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.regenerate_satellite_api_key(
            user_id, organization_id, orbit_id, satellite_id
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_update_in = SatelliteUpdateIn(
        name="updated-name", description="updated-desc"
    )

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    updated_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="updated-name",
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_update_satellite.return_value = updated_satellite

    result = await handler.update_satellite(
        user_id, organization_id, orbit_id, satellite_id, satellite_update_in
    )

    assert result == updated_satellite
    assert result.name == "updated-name"
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_update_satellite.assert_awaited_once()


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_update_in = SatelliteUpdateIn(name="updated-name")
    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.update_satellite(
            user_id, organization_id, orbit_id, satellite_id, satellite_update_in
        )

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.UPDATE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.update_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_satellite_update_failed(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_update_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    satellite_update_in = SatelliteUpdateIn(name="updated-name")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_update_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.update_satellite(
            user_id, organization_id, orbit_id, satellite_id, satellite_update_in
        )

    assert error.value.status_code == 404


@patch(
    "luml.handlers.satellites.SatelliteRepository.delete_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_delete_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_delete_satellite.return_value = None

    await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_delete_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.delete_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite_with_deployments(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
    mock_delete_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_satellite = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite.return_value = mock_satellite
    mock_delete_satellite.side_effect = DatabaseConstraintError(
        "Satellite has deployments"
    )

    with pytest.raises(ApplicationError) as error:
        await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    assert error.value.status_code == 409
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)
    mock_delete_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_satellite_not_found(
    mock_check_permissions: AsyncMock,
    mock_get_satellite: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    mock_get_satellite.return_value = None

    with pytest.raises(NotFoundError, match="Satellite not found") as error:
        await handler.delete_satellite(organization_id, orbit_id, user_id, satellite_id)

    assert error.value.status_code == 404
    mock_check_permissions.assert_awaited_once_with(
        organization_id, user_id, Resource.SATELLITE, Action.DELETE, orbit_id
    )
    mock_get_satellite.assert_awaited_once_with(satellite_id)


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__user_repository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__orbits_repository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites_orbit_member_permissions(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_org_member_role: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "test"}
    }

    expected = [
        Satellite(
            id=satellite_id,
            orbit_id=orbit_id,
            name="test",
            description=None,
            base_url="https://url.com",
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
    ]

    mock_get_org_member_role.return_value = "member"
    mock_get_orbit_member_role.return_value = "member"
    mock_list_satellites.return_value = expected

    result = await handler.list_satellites(user_id, organization_id, orbit_id)

    assert result == expected
    mock_get_org_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_awaited_once_with(orbit_id, user_id)
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.list_satellites",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__user_repository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.satellites.PermissionsHandler._PermissionsHandler__orbits_repository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_list_satellites_organization_admin_permissions(
    mock_get_orbit_member_role: AsyncMock,
    mock_get_org_member_role: AsyncMock,
    mock_list_satellites: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    capabilities: dict[SatelliteCapability, dict[str, Any] | None] = {
        SatelliteCapability.DEPLOY: {"key": "test"}
    }

    expected = [
        Satellite(
            id=satellite_id,
            orbit_id=orbit_id,
            name="test",
            description=None,
            base_url="https://url.com",
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
    ]

    mock_get_org_member_role.return_value = "admin"
    mock_list_satellites.return_value = expected

    result = await handler.list_satellites(user_id, organization_id, orbit_id)

    assert result == expected
    mock_get_org_member_role.assert_awaited_once_with(organization_id, user_id)
    mock_get_orbit_member_role.assert_not_awaited()
    mock_list_satellites.assert_awaited_once_with(orbit_id, None)


@patch(
    "luml.handlers.satellites.SatelliteRepository.get_satellite_by_hash",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_authenticate_api_key(
    mock_get_satellite_by_hash: AsyncMock,
) -> None:
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")
    satellite_id = UUID("0199c418-8be4-737c-a5e4-997685950d42")

    expected = Satellite(
        id=satellite_id,
        orbit_id=orbit_id,
        name="test-satellite",
        description=None,
        base_url="https://url.com",
        paired=True,
        capabilities={SatelliteCapability.DEPLOY: {"key": "test"}},
        created_at=datetime.datetime.now(),
        updated_at=None,
        last_seen_at=None,
    )

    mock_get_satellite_by_hash.return_value = expected

    api_key = "dfssat_test_key_12345"
    result = await handler.authenticate_api_key(api_key)

    assert result == expected
    mock_get_satellite_by_hash.assert_awaited_once()
