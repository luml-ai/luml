from unittest.mock import AsyncMock, Mock

import pytest

from luml.api._types import Orbit
from luml.api.resources.orbits import AsyncOrbitResource, OrbitResource


def test_orbit_list(mock_sync_client: Mock, sample_orbit: Orbit) -> None:
    organization_id = sample_orbit.organization_id
    mock_sync_client.get.return_value = [sample_orbit]

    resource = OrbitResource(mock_sync_client)
    orbits = resource.list()

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits"
    )
    assert len(orbits) == 1
    assert orbits[0].name == sample_orbit.name


def test_orbit_get(mock_sync_client: Mock, sample_orbit: Orbit) -> None:
    organization_id = sample_orbit.organization_id
    orbit_id = mock_sync_client.orbit
    mock_sync_client.get.return_value = sample_orbit

    resource = OrbitResource(mock_sync_client)
    orbit = resource.get()

    mock_sync_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}"
    )
    assert orbit.id == orbit_id


def test_orbit_get_by_name(mock_sync_client: Mock, sample_orbit: Orbit) -> None:
    orbit_name = sample_orbit.name
    mock_sync_client.get.return_value = [sample_orbit]

    resource = OrbitResource(mock_sync_client)
    orbit = resource.get(orbit_name)

    assert orbit.name == orbit_name


def test_orbit_create(mock_sync_client: Mock, sample_orbit: Orbit) -> None:
    organization_id = mock_sync_client.organization
    bucket_id = sample_orbit.bucket_secret_id
    name_orbit_name = sample_orbit.name
    mock_sync_client.post.return_value = sample_orbit

    resource = OrbitResource(mock_sync_client)
    orbit = resource.create(name_orbit_name, bucket_id)

    mock_sync_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits",
        json={"name": name_orbit_name, "bucket_secret_id": bucket_id},
    )
    assert isinstance(orbit, Orbit)
    assert orbit.name == name_orbit_name


def test_orbit_update(mock_sync_client: Mock, sample_orbit: Orbit) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = mock_sync_client.orbit
    orbit_name = sample_orbit.name
    mock_sync_client.patch.return_value = sample_orbit
    mock_sync_client.filter_none.return_value = {"name": orbit_name}

    resource = OrbitResource(mock_sync_client)
    orbit = resource.update(name=orbit_name)

    mock_sync_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}",
        json={"name": orbit_name},
    )
    assert isinstance(orbit, Orbit)
    assert orbit.name == orbit_name


def test_orbit_list_none_response(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = None

    resource = OrbitResource(mock_sync_client)
    orbits = resource.list()

    assert len(orbits) == 0


def test_orbit_delete(mock_sync_client: Mock) -> None:
    organization_id = mock_sync_client.organization
    orbit_id = "019acaac-a0fe-72c8-b51c-43ea970bd0f7"
    mock_sync_client.delete.return_value = None

    resource = OrbitResource(mock_sync_client)
    result = resource.delete(orbit_id)

    mock_sync_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}"
    )
    assert result is None


# Async tests
@pytest.mark.asyncio
async def test_async_orbit_list(
    mock_async_client: AsyncMock, sample_orbit: Orbit
) -> None:
    organization_id = mock_async_client.organization
    mock_async_client.get.return_value = [sample_orbit]

    resource = AsyncOrbitResource(mock_async_client)
    orbits = await resource.list()

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits"
    )
    assert len(orbits) == 1
    assert orbits[0].name == sample_orbit.name


@pytest.mark.asyncio
async def test_async_orbit_get(
    mock_async_client: AsyncMock, sample_orbit: Orbit
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    mock_async_client.get.return_value = sample_orbit

    resource = AsyncOrbitResource(mock_async_client)
    orbit = await resource.get()

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}"
    )
    assert orbit.id == orbit_id


@pytest.mark.asyncio
async def test_async_orbit_get_by_id(
    mock_async_client: AsyncMock, sample_orbit: Orbit
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = sample_orbit.id
    mock_async_client.get.return_value = sample_orbit

    resource = AsyncOrbitResource(mock_async_client)
    orbit = await resource.get(orbit_id)  # Specific ID

    mock_async_client.get.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}"
    )
    assert orbit.id == orbit_id


@pytest.mark.asyncio
async def test_async_orbit_get_by_name(
    mock_async_client: AsyncMock, sample_orbit: Orbit
) -> None:
    orbit_name = sample_orbit.name
    mock_async_client.get.return_value = [sample_orbit]

    resource = AsyncOrbitResource(mock_async_client)
    orbit = await resource.get(orbit_name)

    assert orbit.name == orbit_name


@pytest.mark.asyncio
async def test_async_orbit_list_none_response(mock_async_client: AsyncMock) -> None:
    mock_async_client.get.return_value = None

    resource = AsyncOrbitResource(mock_async_client)
    orbits = await resource.list()

    assert len(orbits) == 0


@pytest.mark.asyncio
async def test_async_orbit_create(
    mock_async_client: AsyncMock, sample_orbit: Orbit
) -> None:
    organization_id = mock_async_client.organization
    bucket_id = sample_orbit.bucket_secret_id
    orbit_name = sample_orbit.name
    mock_async_client.post.return_value = sample_orbit

    resource = AsyncOrbitResource(mock_async_client)
    orbit = await resource.create(orbit_name, bucket_id)

    mock_async_client.post.assert_called_once_with(
        f"/organizations/{organization_id}/orbits",
        json={"name": orbit_name, "bucket_secret_id": bucket_id},
    )
    assert isinstance(orbit, Orbit)
    assert orbit.name == orbit_name


@pytest.mark.asyncio
async def test_async_orbit_update(
    mock_async_client: AsyncMock, sample_orbit: Orbit
) -> None:
    organization_id = mock_async_client.organization
    orbit_id = mock_async_client.orbit
    orbit_name = sample_orbit.name
    mock_async_client.patch.return_value = sample_orbit
    mock_async_client.filter_none.return_value = {"name": orbit_name}

    resource = AsyncOrbitResource(mock_async_client)
    orbit = await resource.update(name=orbit_name)

    mock_async_client.patch.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}",
        json={"name": orbit_name},
    )
    assert isinstance(orbit, Orbit)
    assert orbit.name == orbit_name


@pytest.mark.asyncio
async def test_async_orbit_delete(mock_async_client: AsyncMock) -> None:
    organization_id = mock_async_client.organization
    orbit_id = "c2cb9f9d-474b-4b57-a318-7755edb61d76"
    mock_async_client.delete.return_value = None

    resource = AsyncOrbitResource(mock_async_client)
    result = await resource.delete(orbit_id)

    mock_async_client.delete.assert_called_once_with(
        f"/organizations/{organization_id}/orbits/{orbit_id}"
    )
    assert result is None
