import uuid

import pytest
from luml.infra.exceptions import InvalidStatusTransitionError
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.deployment import (
    DeploymentCreate,
    DeploymentDetailsUpdate,
    DeploymentStatus,
    DeploymentUpdate,
    MonitoringMode,
)
from luml.schemas.satellite import SatelliteTaskType
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import SatelliteFixtureData


class TestDeploymentRepositoryUpdates:
    async def test_update_deployment_applies_given_fields(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created_deployment, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                tags=["original"],
            )
        )

        update_data = DeploymentUpdate(
            id=created_deployment.id,
            inference_url=f"https://test-inference{uuid.uuid4()}.com/api",
            status=DeploymentStatus.ACTIVE,
            tags=["updated", "active"],
        )
        updated_deployment = await repository.update_deployment(
            created_deployment.id, seeded_satellite.satellite.id, update_data
        )

        assert updated_deployment
        assert updated_deployment.id == created_deployment.id
        assert updated_deployment.inference_url == update_data.inference_url
        assert updated_deployment.status == update_data.status
        assert updated_deployment.tags == update_data.tags
        assert updated_deployment.collection_id == seeded_satellite.model.collection_id
        assert updated_deployment.provider_ref is None
        assert updated_deployment.progress_note is None

    async def test_update_deployment_keeps_provider_ref_when_progress_note_cleared(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployment, _ = await repository.create_deployment(
            DeploymentCreate(
                name="provider-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
            )
        )

        pending = await repository.update_deployment(
            deployment.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(
                id=deployment.id,
                provider_ref="provider-job-123",
                progress_note="Creating workload",
            ),
        )
        active = await repository.update_deployment(
            deployment.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(
                id=deployment.id,
                status=DeploymentStatus.ACTIVE,
                progress_note=None,
            ),
        )

        assert pending is not None
        assert pending.provider_ref == "provider-job-123"
        assert pending.progress_note == "Creating workload"
        assert active is not None
        assert active.provider_ref == "provider-job-123"
        assert active.progress_note is None

    async def test_update_deployment_allows_two_deployments_to_share_inference_url(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        deployments = [
            (
                await repository.create_deployment(
                    DeploymentCreate(
                        name=f"shared-address-{index}",
                        orbit_id=seeded_satellite.orbit.id,
                        satellite_id=seeded_satellite.satellite.id,
                        artifact_id=seeded_satellite.model.id,
                    )
                )
            )[0]
            for index in range(2)
        ]
        inference_url = "https://multi-model.example/inference"

        updated = [
            await repository.update_deployment(
                deployment.id,
                seeded_satellite.satellite.id,
                DeploymentUpdate(id=deployment.id, inference_url=inference_url),
            )
            for deployment in deployments
        ]

        assert [deployment.inference_url for deployment in updated if deployment] == [
            inference_url,
            inference_url,
        ]

    async def test_update_deployment_preserves_omitted_fields_and_clears_explicit_null(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="monitored-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
            )
        )
        inference_url = f"https://inference-{uuid.uuid4()}.example/api"
        await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(
                id=created.id,
                inference_url=inference_url,
                status=DeploymentStatus.ACTIVE,
            ),
        )

        monitored = await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(
                id=created.id,
                monitoring_url=f"/deployments/{created.id}/monitoring",
            ),
        )

        assert monitored is not None
        assert monitored.monitoring_url == f"/deployments/{created.id}/monitoring"
        assert monitored.inference_url == inference_url
        assert monitored.status == DeploymentStatus.ACTIVE

        cleared = await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(id=created.id, monitoring_url=None),
        )

        assert cleared is not None
        assert cleared.monitoring_url is None
        assert cleared.inference_url == inference_url
        assert cleared.status == DeploymentStatus.ACTIVE

    async def test_update_deployment_keeps_routing_metadata_when_only_status_set(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                tags=["routed"],
            )
        )
        inference_url = f"https://test-inference{uuid.uuid4()}.com/api"
        await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(
                id=created.id,
                inference_url=inference_url,
                schemas={"openapi": "3.0.0"},
                status=DeploymentStatus.ACTIVE,
            ),
        )

        updated = await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(id=created.id, status=DeploymentStatus.NOT_RESPONDING),
        )

        assert updated
        assert updated.status == DeploymentStatus.NOT_RESPONDING
        assert updated.inference_url == inference_url
        assert updated.schemas == {"openapi": "3.0.0"}
        assert updated.tags == ["routed"]

    async def test_update_deployment_blocks_leaving_deletion_but_accepts_its_failure(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
            )
        )
        await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(id=created.id, status=DeploymentStatus.DELETION_PENDING),
        )

        with pytest.raises(InvalidStatusTransitionError):
            await repository.update_deployment(
                created.id,
                seeded_satellite.satellite.id,
                DeploymentUpdate(id=created.id, status=DeploymentStatus.ACTIVE),
            )

        updated = await repository.update_deployment(
            created.id,
            seeded_satellite.satellite.id,
            DeploymentUpdate(
                id=created.id,
                status=DeploymentStatus.DELETION_FAILED,
                error_message={"reason": "x", "error": "y"},
            ),
        )
        assert updated
        assert updated.status == DeploymentStatus.DELETION_FAILED

    async def test_update_deployment_raises_and_keeps_status_when_status_set_to_null(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
            )
        )

        with pytest.raises(InvalidStatusTransitionError):
            await repository.update_deployment(
                created.id,
                seeded_satellite.satellite.id,
                DeploymentUpdate(id=created.id, status=None),
            )

        unchanged = await repository.get_deployment(
            created.id, seeded_satellite.orbit.id
        )
        assert unchanged
        assert unchanged.status == DeploymentStatus.PENDING

    async def test_update_deployment_details_applies_given_fields(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        created_deployment, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                status=DeploymentStatus.PENDING,
                tags=["original"],
            )
        )

        details = DeploymentDetailsUpdate(
            name="my-deployment",
            description="some desc",
            dynamic_attributes_secrets={"token": str(uuid.uuid7())},
            tags=["one", "two"],
        )

        updated = await repository.update_deployment_details(
            seeded_satellite.orbit.id, created_deployment.id, details
        )

        assert updated is not None
        assert updated.id == created_deployment.id
        assert updated.name == details.name
        assert updated.description == details.description
        assert updated.dynamic_attributes_secrets == details.dynamic_attributes_secrets
        assert updated.tags == details.tags
        assert updated.collection_id == seeded_satellite.model.collection_id

    async def test_update_deployment_details_enqueues_reconcile_when_monitoring_changes(
        self,
        repository: DeploymentRepository,
        engine: AsyncEngine,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        satellite_repository = SatelliteRepository(engine)

        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                monitoring_mode=MonitoringMode.OFF,
            )
        )

        updated = await repository.update_deployment_details(
            seeded_satellite.orbit.id,
            created.id,
            DeploymentDetailsUpdate(monitoring_mode=MonitoringMode.FULL),
        )

        assert updated is not None
        assert updated.monitoring_mode == MonitoringMode.FULL

        tasks = await satellite_repository.list_tasks(seeded_satellite.satellite.id)
        reconcile_tasks = [t for t in tasks if t.type == SatelliteTaskType.RECONCILE]
        assert len(reconcile_tasks) == 1
        assert reconcile_tasks[0].payload["deployment_id"] == str(created.id)

    async def test_update_deployment_details_enqueues_no_reconcile_when_mode_unchanged(
        self,
        repository: DeploymentRepository,
        engine: AsyncEngine,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        satellite_repository = SatelliteRepository(engine)

        created, _ = await repository.create_deployment(
            DeploymentCreate(
                name="my-deployment",
                orbit_id=seeded_satellite.orbit.id,
                satellite_id=seeded_satellite.satellite.id,
                artifact_id=seeded_satellite.model.id,
                monitoring_mode=MonitoringMode.FULL,
            )
        )

        await repository.update_deployment_details(
            seeded_satellite.orbit.id,
            created.id,
            DeploymentDetailsUpdate(
                description="new", monitoring_mode=MonitoringMode.FULL
            ),
        )

        tasks = await satellite_repository.list_tasks(seeded_satellite.satellite.id)
        assert [t for t in tasks if t.type == SatelliteTaskType.RECONCILE] == []

    async def test_update_operations_return_none_when_deployment_unknown(
        self, repository: DeploymentRepository, seeded_satellite: SatelliteFixtureData
    ) -> None:
        missing_id = uuid.uuid7()

        assert (
            await repository.update_deployment(
                missing_id,
                seeded_satellite.satellite.id,
                DeploymentUpdate(id=missing_id, status=DeploymentStatus.ACTIVE),
            )
            is None
        )
        assert (
            await repository.request_deployment_deletion(
                seeded_satellite.orbit.id, missing_id
            )
            is None
        )
        assert (
            await repository.update_deployment_details(
                seeded_satellite.orbit.id,
                missing_id,
                DeploymentDetailsUpdate(name="renamed"),
            )
            is None
        )
        assert await repository.enqueue_undeploy_task(missing_id) is None
