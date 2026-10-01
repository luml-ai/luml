import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from luml.handlers.deployments import DeploymentHandler
from luml.infra.db import engine as shared_engine
from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import (
    DeploymentCreate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
)

from tests.conftest import SatelliteFixtureData


@pytest_asyncio.fixture
async def deployment_handler() -> AsyncGenerator[DeploymentHandler]:
    await shared_engine.dispose()
    yield DeploymentHandler()
    await shared_engine.dispose()


@patch(
    "luml.handlers.deployments.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_partial_details_update_preserves_untouched_columns(
    mock_check_permissions: AsyncMock,  # noqa: ARG001
    create_satellite: SatelliteFixtureData,
    deployment_handler: DeploymentHandler,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)
    secret_id = str(uuid.uuid7())

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="original",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
            description="keep me",
            tags=["keep"],
            dynamic_attributes_secrets={"token": secret_id},
            env_variables={"LEVEL": "debug"},
        )
    )

    await deployment_handler.update_deployment_details(
        data.user.id,
        data.organization.id,
        data.orbit.id,
        created.id,
        DeploymentDetailsUpdateIn(name="renamed"),
    )

    reloaded = await repo.get_deployment(created.id, data.orbit.id)
    assert reloaded is not None
    assert reloaded.name == "renamed"
    assert reloaded.description == "keep me"
    assert reloaded.tags == ["keep"]
    assert reloaded.dynamic_attributes_secrets == {"token": secret_id}
    assert reloaded.env_variables == {"LEVEL": "debug"}


@patch(
    "luml.handlers.deployments.PermissionsHandler.check_permissions",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_details_update_treats_explicit_null_secrets_as_cleared(
    mock_check_permissions: AsyncMock,  # noqa: ARG001
    create_satellite: SatelliteFixtureData,
    deployment_handler: DeploymentHandler,
) -> None:
    data = create_satellite
    repo = DeploymentRepository(data.engine)

    created, _ = await repo.create_deployment(
        DeploymentCreate(
            name="original",
            orbit_id=data.orbit.id,
            satellite_id=data.satellite.id,
            artifact_id=data.model.id,
            status=DeploymentStatus.PENDING,
            dynamic_attributes_secrets={"token": str(uuid.uuid7())},
        )
    )

    await deployment_handler.update_deployment_details(
        data.user.id,
        data.organization.id,
        data.orbit.id,
        created.id,
        DeploymentDetailsUpdateIn.model_validate({"dynamic_attributes_secrets": None}),
    )

    reloaded = await repo.get_deployment(created.id, data.orbit.id)
    assert reloaded is not None
    assert reloaded.dynamic_attributes_secrets == {}
