import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from dataforce_studio.repositories.orbit_secrets import OrbitSecretRepository
from dataforce_studio.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretUpdate,
)
from tests.conftest import OrbitFixtureData


@pytest.mark.asyncio
async def test_create_orbit_secret(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit

    repo = OrbitSecretRepository(engine)

    secret_data = OrbitSecretCreate(name="test", value="secret", orbit_id=orbit.id)
    orbit_secret = await repo.create_orbit_secret(secret_data)

    assert orbit_secret
    assert orbit_secret.orbit_id == orbit.id


@pytest.mark.asyncio
async def test_get_orbit_secret(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = OrbitSecretRepository(engine)

    secret_data = OrbitSecretCreate(name="test", value="secret", orbit_id=orbit.id)
    secret = await repo.create_orbit_secret(secret_data)
    fetched_secret = await repo.get_orbit_secret(secret.id)

    assert fetched_secret
    assert isinstance(fetched_secret, OrbitSecret)
    assert secret.id == fetched_secret.id
    assert secret.orbit_id == fetched_secret.orbit_id
    assert fetched_secret.name == secret_data.name
    assert fetched_secret.value == secret_data.value


@pytest.mark.asyncio
async def test_get_orbit_secret_not_found(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = OrbitSecretRepository(engine)

    fetched_secret = await repo.get_orbit_secret(99999999)

    assert fetched_secret is None


@pytest.mark.asyncio
async def test_get_orbit_secrets(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = OrbitSecretRepository(engine)

    secret_data = OrbitSecretCreate(name="test", value="secret", orbit_id=orbit.id)
    await repo.create_orbit_secret(secret_data)

    all_secrets = await repo.get_orbit_secrets(orbit.id)

    assert len(all_secrets) == 1
    assert isinstance(all_secrets[0], OrbitSecret)
    assert all_secrets[0].orbit_id == orbit.id


@pytest.mark.asyncio
async def test_delete_orbit_secrets(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = OrbitSecretRepository(engine)

    secret_data = OrbitSecretCreate(name="test", value="secret", orbit_id=orbit.id)
    secret = await repo.create_orbit_secret(secret_data)

    assert secret.id

    await repo.delete_orbit_secret(secret.id)
    fetched_secret = await repo.get_orbit_secret(secret.id)

    assert fetched_secret is None


@pytest.mark.asyncio
async def test_update_orbit_secret(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = OrbitSecretRepository(engine)

    secret_data = OrbitSecretCreate(name="test", value="secret", orbit_id=orbit.id)
    created_secret = await repo.create_orbit_secret(secret_data)

    update_data = OrbitSecretUpdate(name="fully_updated", value="new_secret_value")
    updated_secret = await repo.update_orbit_secret(created_secret.id, update_data)

    assert updated_secret is not None
    assert updated_secret.id == created_secret.id
    assert updated_secret.name == "fully_updated"
    assert updated_secret.value == "new_secret_value"
    assert updated_secret.orbit_id == orbit.id


@pytest.mark.asyncio
async def test_update_orbit_secret_not_found(
    create_database_and_apply_migrations: str,
) -> None:
    engine = create_async_engine(create_database_and_apply_migrations)
    repo = OrbitSecretRepository(engine)

    update_data = OrbitSecretUpdate(name="test", value="secret")
    result = await repo.update_orbit_secret(99999999, update_data)

    assert result is None
