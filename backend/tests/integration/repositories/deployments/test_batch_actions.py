from uuid import uuid7

import pytest
from luml.infra.exceptions import InvalidStatusTransitionError
from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus, DeploymentUpdate

from tests.support.seeds import SatelliteFixtureData


@pytest.mark.parametrize("current_status", list(DeploymentStatus))
async def test_force_delete_checks_current_status_and_orbit(
    repository: DeploymentRepository,
    seeded_satellite: SatelliteFixtureData,
    current_status: DeploymentStatus,
) -> None:
    deployment, _ = await repository.create_deployment(
        DeploymentCreate(
            name="selected deployment",
            orbit_id=seeded_satellite.orbit.id,
            satellite_id=seeded_satellite.satellite.id,
            artifact_id=seeded_satellite.model.id,
            status=DeploymentStatus.PENDING,
        )
    )
    await repository.update_deployment(
        deployment.id,
        deployment.satellite_id,
        DeploymentUpdate(id=deployment.id, status=current_status),
    )
    assert (
        await repository.force_delete_inactive_deployment(deployment.id, uuid7())
        is None
    )
    if current_status == DeploymentStatus.ACTIVE:
        with pytest.raises(
            InvalidStatusTransitionError, match="Stop active deployments first"
        ):
            await repository.force_delete_inactive_deployment(
                deployment.id, deployment.orbit_id
            )
        assert (
            await repository.get_deployment(deployment.id, deployment.orbit_id)
            is not None
        )
    else:
        assert (
            await repository.force_delete_inactive_deployment(
                deployment.id, deployment.orbit_id
            )
            is not None
        )
        assert (
            await repository.get_deployment(deployment.id, deployment.orbit_id) is None
        )
