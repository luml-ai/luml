from uuid import uuid7

import pytest
from luml.infra.exceptions import OrbitSecretInUseError
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus
from luml.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretUpdate,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_sibling_orbit
from tests.support.seeds import OrbitFixtureData, SatelliteFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> OrbitSecretRepository:
    return OrbitSecretRepository(engine)


class TestOrbitSecretRepository:
    async def test_create_orbit_secret_returns_secret_of_orbit(
        self, repository: OrbitSecretRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        secret_data = OrbitSecretCreate(
            name="test", value="secret", orbit_id=seeded_orbit.orbit.id
        )
        orbit_secret = await repository.create_orbit_secret(secret_data)

        assert orbit_secret
        assert orbit_secret.orbit_id == seeded_orbit.orbit.id

    async def test_get_orbit_secret_returns_stored_secret(
        self, repository: OrbitSecretRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        secret_data = OrbitSecretCreate(
            name="test", value="secret", orbit_id=seeded_orbit.orbit.id
        )
        secret = await repository.create_orbit_secret(secret_data)
        fetched_secret = await repository.get_orbit_secret(
            secret.id, seeded_orbit.orbit.id
        )

        assert fetched_secret
        assert isinstance(fetched_secret, OrbitSecret)
        assert secret.id == fetched_secret.id
        assert secret.orbit_id == fetched_secret.orbit_id
        assert fetched_secret.name == secret_data.name
        assert fetched_secret.value == secret_data.value

    async def test_get_orbit_secret_returns_none_when_not_found(
        self, repository: OrbitSecretRepository
    ) -> None:
        fetched_secret = await repository.get_orbit_secret(uuid7(), uuid7())

        assert fetched_secret is None

    async def test_get_orbit_secrets_returns_secrets_of_orbit(
        self, repository: OrbitSecretRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        secret_data = OrbitSecretCreate(
            name="test", value="secret", orbit_id=seeded_orbit.orbit.id
        )
        await repository.create_orbit_secret(secret_data)

        all_secrets = await repository.get_orbit_secrets(seeded_orbit.orbit.id)

        assert len(all_secrets) == 1
        assert isinstance(all_secrets[0], OrbitSecret)
        assert all_secrets[0].orbit_id == seeded_orbit.orbit.id

    async def test_delete_orbit_secret_removes_secret(
        self, repository: OrbitSecretRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        secret_data = OrbitSecretCreate(
            name="test", value="secret", orbit_id=seeded_orbit.orbit.id
        )
        secret = await repository.create_orbit_secret(secret_data)

        assert secret.id

        assert (
            await repository.delete_orbit_secret(secret.id, seeded_orbit.orbit.id)
            is True
        )
        fetched_secret = await repository.get_orbit_secret(
            secret.id, seeded_orbit.orbit.id
        )

        assert fetched_secret is None

    async def test_update_orbit_secret_replaces_name_and_value(
        self, repository: OrbitSecretRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        secret_data = OrbitSecretCreate(
            name="test", value="secret", orbit_id=seeded_orbit.orbit.id
        )
        created_secret = await repository.create_orbit_secret(secret_data)

        update_data = OrbitSecretUpdate(name="fully_updated", value="new_secret_value")
        updated_secret = await repository.update_orbit_secret(
            created_secret.id, seeded_orbit.orbit.id, update_data
        )

        assert updated_secret is not None
        assert updated_secret.id == created_secret.id
        assert updated_secret.name == "fully_updated"
        assert updated_secret.value == "new_secret_value"
        assert updated_secret.orbit_id == seeded_orbit.orbit.id

    async def test_update_orbit_secret_returns_none_when_not_found(
        self, repository: OrbitSecretRepository
    ) -> None:
        update_data = OrbitSecretUpdate(name="test", value="secret")
        result = await repository.update_orbit_secret(uuid7(), uuid7(), update_data)

        assert result is None

    async def test_get_orbit_secret_returns_none_when_orbit_differs(
        self,
        repository: OrbitSecretRepository,
        engine: AsyncEngine,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        sibling_orbit = await create_sibling_orbit(
            engine, seeded_orbit.organization.id, seeded_orbit.bucket_secret.id
        )

        secret = await repository.create_orbit_secret(
            OrbitSecretCreate(
                name="test", value="secret", orbit_id=seeded_orbit.orbit.id
            )
        )

        assert await repository.get_orbit_secret(secret.id, sibling_orbit.id) is None
        assert (
            await repository.get_orbit_secret(secret.id, seeded_orbit.orbit.id)
            is not None
        )

    async def test_update_orbit_secret_returns_none_when_orbit_differs(
        self,
        repository: OrbitSecretRepository,
        engine: AsyncEngine,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        sibling_orbit = await create_sibling_orbit(
            engine, seeded_orbit.organization.id, seeded_orbit.bucket_secret.id
        )

        secret = await repository.create_orbit_secret(
            OrbitSecretCreate(
                name="test", value="secret", orbit_id=seeded_orbit.orbit.id
            )
        )

        result = await repository.update_orbit_secret(
            secret.id,
            sibling_orbit.id,
            OrbitSecretUpdate(name="renamed", value="renamed_value"),
        )

        assert result is None

        untouched = await repository.get_orbit_secret(secret.id, seeded_orbit.orbit.id)
        assert untouched is not None
        assert untouched.name == "test"
        assert untouched.value == "secret"

    async def test_delete_orbit_secret_returns_false_when_orbit_differs(
        self,
        repository: OrbitSecretRepository,
        engine: AsyncEngine,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        sibling_orbit = await create_sibling_orbit(
            engine, seeded_orbit.organization.id, seeded_orbit.bucket_secret.id
        )

        secret = await repository.create_orbit_secret(
            OrbitSecretCreate(
                name="test", value="secret", orbit_id=seeded_orbit.orbit.id
            )
        )

        assert (
            await repository.delete_orbit_secret(secret.id, sibling_orbit.id) is False
        )
        assert (
            await repository.get_orbit_secret(secret.id, seeded_orbit.orbit.id)
            is not None
        )

    @pytest.mark.parametrize(
        "binding", ["dynamic_attributes_secrets", "env_variables_secrets"]
    )
    async def test_delete_orbit_secret_raises_in_use_when_deployment_binds_it(
        self,
        repository: OrbitSecretRepository,
        seeded_satellite: SatelliteFixtureData,
        binding: str,
    ) -> None:
        secret = await repository.create_orbit_secret(
            OrbitSecretCreate(
                name="token", value="secret", orbit_id=seeded_satellite.orbit.id
            )
        )
        await DeploymentRepository(seeded_satellite.engine).create_deployment(
            DeploymentCreate(
                name="uses-token",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                **{binding: {"TOKEN": str(secret.id)}},
            )
        )

        with pytest.raises(OrbitSecretInUseError) as error:
            await repository.delete_orbit_secret(secret.id, seeded_satellite.orbit.id)

        assert error.value.status_code == 409
        assert error.value.deployment_names == ["uses-token"]
        assert "uses-token" in error.value.message
        assert (
            await repository.get_orbit_secret(secret.id, seeded_satellite.orbit.id)
            is not None
        )

    async def test_delete_orbit_secret_ignores_deployments_bound_to_other_secrets(
        self,
        repository: OrbitSecretRepository,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        orbit_id = seeded_satellite.orbit.id
        secret = await repository.create_orbit_secret(
            OrbitSecretCreate(name="unused", value="secret", orbit_id=orbit_id)
        )
        other = await repository.create_orbit_secret(
            OrbitSecretCreate(name="used", value="secret", orbit_id=orbit_id)
        )
        await DeploymentRepository(seeded_satellite.engine).create_deployment(
            DeploymentCreate(
                name="uses-other",
                orbit_id=orbit_id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                dynamic_attributes_secrets={"token": str(other.id)},
            )
        )

        assert await repository.delete_orbit_secret(secret.id, orbit_id) is True
        assert await repository.get_orbit_secret(secret.id, orbit_id) is None
