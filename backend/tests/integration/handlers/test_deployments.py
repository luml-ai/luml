import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from luml.handlers.deployments import DeploymentHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine as shared_engine
from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import (
    DeploymentCreate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import SatelliteFixtureData


@pytest.fixture
def repository(engine: AsyncEngine) -> DeploymentRepository:
    return DeploymentRepository(engine)


@pytest.fixture
async def handler(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[DeploymentHandler]:
    monkeypatch.setattr(PermissionsHandler, "check_permissions", AsyncMock())
    await shared_engine.dispose()
    yield DeploymentHandler()
    await shared_engine.dispose()


class TestDeploymentHandler:
    async def test_update_deployment_details_preserves_untouched_columns_when_partial(
        self,
        handler: DeploymentHandler,
        repository: DeploymentRepository,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        secret_id = str(uuid.uuid7())
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="original",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                description="keep me",
                tags=["keep"],
                dynamic_attributes_secrets={"token": secret_id},
                env_variables={"LEVEL": "debug"},
            )
        )

        await handler.update_deployment_details(
            seeded_satellite.user.id,
            seeded_satellite.organization.id,
            seeded_satellite.orbit.id,
            created.id,
            DeploymentDetailsUpdateIn(name="renamed"),
        )

        reloaded = await repository.get_deployment(
            created.id, seeded_satellite.orbit.id
        )
        assert reloaded is not None
        assert reloaded.name == "renamed"
        assert reloaded.description == "keep me"
        assert reloaded.tags == ["keep"]
        assert reloaded.dynamic_attributes_secrets == {"token": secret_id}
        assert reloaded.env_variables == {"LEVEL": "debug"}

    async def test_update_deployment_details_clears_secrets_when_explicit_null(
        self,
        handler: DeploymentHandler,
        repository: DeploymentRepository,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="original",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                dynamic_attributes_secrets={"token": str(uuid.uuid7())},
            )
        )

        await handler.update_deployment_details(
            seeded_satellite.user.id,
            seeded_satellite.organization.id,
            seeded_satellite.orbit.id,
            created.id,
            DeploymentDetailsUpdateIn.model_validate(
                {"dynamic_attributes_secrets": None}
            ),
        )

        reloaded = await repository.get_deployment(
            created.id, seeded_satellite.orbit.id
        )
        assert reloaded is not None
        assert reloaded.dynamic_attributes_secrets == {}
