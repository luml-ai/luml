from uuid import uuid7

import pytest
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.orbit import OrbitCreateIn, OrbitDetails
from luml.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretUpdate,
)
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import OrbitFixtureData


async def _create_sibling_orbit(data: OrbitFixtureData) -> OrbitDetails:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="sibling orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert orbit is not None
    return orbit


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
    fetched_secret = await repo.get_orbit_secret(secret.id, orbit.id)

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

    fetched_secret = await repo.get_orbit_secret(uuid7(), uuid7())

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

    assert await repo.delete_orbit_secret(secret.id, orbit.id) is True
    fetched_secret = await repo.get_orbit_secret(secret.id, orbit.id)

    assert fetched_secret is None


@pytest.mark.asyncio
async def test_update_orbit_secret(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    engine, orbit = data.engine, data.orbit
    repo = OrbitSecretRepository(engine)

    secret_data = OrbitSecretCreate(name="test", value="secret", orbit_id=orbit.id)
    created_secret = await repo.create_orbit_secret(secret_data)

    update_data = OrbitSecretUpdate(name="fully_updated", value="new_secret_value")
    updated_secret = await repo.update_orbit_secret(
        created_secret.id, orbit.id, update_data
    )

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
    result = await repo.update_orbit_secret(uuid7(), uuid7(), update_data)

    assert result is None


@pytest.mark.asyncio
async def test_get_orbit_secret_from_another_orbit(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = OrbitSecretRepository(data.engine)
    sibling_orbit = await _create_sibling_orbit(data)

    secret = await repo.create_orbit_secret(
        OrbitSecretCreate(name="test", value="secret", orbit_id=data.orbit.id)
    )

    assert await repo.get_orbit_secret(secret.id, sibling_orbit.id) is None
    assert await repo.get_orbit_secret(secret.id, data.orbit.id) is not None


@pytest.mark.asyncio
async def test_update_orbit_secret_from_another_orbit(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = OrbitSecretRepository(data.engine)
    sibling_orbit = await _create_sibling_orbit(data)

    secret = await repo.create_orbit_secret(
        OrbitSecretCreate(name="test", value="secret", orbit_id=data.orbit.id)
    )

    result = await repo.update_orbit_secret(
        secret.id,
        sibling_orbit.id,
        OrbitSecretUpdate(name="renamed", value="renamed_value"),
    )

    assert result is None

    untouched = await repo.get_orbit_secret(secret.id, data.orbit.id)
    assert untouched is not None
    assert untouched.name == "test"
    assert untouched.value == "secret"


@pytest.mark.asyncio
async def test_delete_orbit_secret_from_another_orbit(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = OrbitSecretRepository(data.engine)
    sibling_orbit = await _create_sibling_orbit(data)

    secret = await repo.create_orbit_secret(
        OrbitSecretCreate(name="test", value="secret", orbit_id=data.orbit.id)
    )

    assert await repo.delete_orbit_secret(secret.id, sibling_orbit.id) is False
    assert await repo.get_orbit_secret(secret.id, data.orbit.id) is not None
