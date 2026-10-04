from luml.repositories.deployments import DeploymentRepository
from luml.schemas.deployment import DeploymentCreate, DeploymentStatus

from tests.support.seeds import SatelliteFixtureData


class TestDeploymentRepositoryListing:
    async def test_list_deployments_returns_orbit_deployments(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment_data = DeploymentCreate(
            name="my-deployment",
            orbit_id=seeded_satellite.orbit.id,
            satellite_id=seeded_satellite.satellite.id,
            artifact_id=seeded_satellite.model.id,
            status=DeploymentStatus.PENDING,
            created_by_user="test_user",
            tags=["test", "deployment"],
        )

        created_dep1, _ = await repository.create_deployment(deployment_data)

        deployment_data.status = DeploymentStatus.ACTIVE
        created_dep2, _ = await repository.create_deployment(deployment_data)

        deployments = await repository.list_deployments(seeded_satellite.orbit.id)

        assert len(deployments) == 2
        deployment_ids = [d.id for d in deployments]
        assert created_dep1.id in deployment_ids
        assert created_dep2.id in deployment_ids
        for d in deployments:
            assert d.collection_id == seeded_satellite.model.collection_id

    async def test_list_satellite_deployments_returns_satellite_deployments(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployments_num = 4
        deployments = []

        for _ in range(deployments_num):
            deployment, _ = await repository.create_deployment(
                DeploymentCreate(
                    name="my-deployment",
                    orbit_id=seeded_satellite.orbit.id,
                    satellite_id=seeded_satellite.satellite.id,
                    artifact_id=seeded_satellite.model.id,
                    status=DeploymentStatus.PENDING,
                )
            )
            deployments.append(deployment)

        all_deployments = await repository.list_satellite_deployments(
            seeded_satellite.satellite.id
        )
        ids = [d.id for d in all_deployments]
        assert len(all_deployments) == deployments_num
        assert all(dep.id in ids for dep in deployments)
        assert all(
            d.collection_id == seeded_satellite.model.collection_id
            for d in all_deployments
        )
