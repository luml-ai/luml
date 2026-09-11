from uuid import UUID

from fastapi import status

from luml.handlers.api_keys import APIKeyHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import Artifact
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentCreateIn,
    DeploymentDetailsUpdate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
    DeploymentUpdate,
    DeploymentUpdateIn,
    MonitoringMode,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import (
    DEPLOY_CAPABILITY,
    MONITORING_CAPABILITY,
    DeployCapabilityV1,
    Satellite,
    SatelliteQueueTask,
)


class DeploymentHandler:
    __repo = DeploymentRepository(engine)
    __sat_repo = SatelliteRepository(engine)
    __orbit_repo = OrbitRepository(engine)
    __artifact_repo = ArtifactRepository(engine)
    __collection_repo = CollectionRepository(engine)
    __secret_repo = BucketSecretRepository(engine)
    __user_repo = UserRepository(engine)
    __permissions_handler = PermissionsHandler()
    __api_key_handler = APIKeyHandler()

    @staticmethod
    def _convert_dynamic_attributes_secrets(
        dynamic_attributes: dict[str, UUID],
    ) -> dict[str, str]:
        return {k: str(v) for k, v in (dynamic_attributes or {}).items()}

    @staticmethod
    def _require_present_capability(
        satellite: Satellite,
        capability: str,
    ) -> None:
        if capability not in satellite.present_capabilities:
            raise ApplicationError(
                f"Satellite does not have a present '{capability}' capability",
                status.HTTP_409_CONFLICT,
            )

    @classmethod
    def _validate_create_capabilities(
        cls,
        satellite: Satellite,
        artifact: Artifact,
        monitoring_mode: MonitoringMode,
    ) -> None:
        cls._require_present_capability(satellite, DEPLOY_CAPABILITY)
        deploy = DeployCapabilityV1.model_validate(
            satellite.capabilities[DEPLOY_CAPABILITY]
        )
        if artifact.manifest.variant not in deploy.supported_variants:
            raise ApplicationError(
                f"Artifact variant '{artifact.manifest.variant}' is not in deploy "
                "supported_variants",
                status.HTTP_409_CONFLICT,
            )

        tag_combinations = deploy.supported_tags_combinations
        producer_tags = set(artifact.manifest.producer_tags)
        if tag_combinations is not None and not any(
            all(tag in producer_tags for tag in combination)
            for combination in tag_combinations
        ):
            raise ApplicationError(
                "Artifact producer tags do not satisfy deploy "
                "supported_tags_combinations",
                status.HTTP_409_CONFLICT,
            )

        if monitoring_mode != MonitoringMode.OFF:
            cls._require_present_capability(satellite, MONITORING_CAPABILITY)

    async def create_deployment(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        data: DeploymentCreateIn,
    ) -> Deployment:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.CREATE,
            orbit_id,
        )

        orbit = await self.__orbit_repo.get_orbit_simple(orbit_id, organization_id)
        if not orbit:
            raise NotFoundError("Orbit not found")

        satellite = await self.__sat_repo.get_satellite(data.satellite_id)
        if not satellite or satellite.orbit_id != orbit_id:
            raise NotFoundError("Satellite not found")

        artifact = await self.__artifact_repo.get_artifact(data.artifact_id)
        if not artifact:
            raise NotFoundError("Artifact not found")

        collection = await self.__collection_repo.get_collection(artifact.collection_id)
        if not collection or collection.orbit_id != orbit_id:
            raise NotFoundError("Collection not found")

        user = await self.__user_repo.get_public_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        self._validate_create_capabilities(
            satellite,
            artifact,
            data.monitoring_mode,
        )

        deployment, _ = await self.__repo.create_deployment(
            DeploymentCreate(
                orbit_id=orbit_id,
                satellite_id=data.satellite_id,
                artifact_id=data.artifact_id,
                name=data.name,
                monitoring_mode=data.monitoring_mode,
                satellite_parameters=data.satellite_parameters,
                description=data.description,
                dynamic_attributes_secrets=self._convert_dynamic_attributes_secrets(
                    data.dynamic_attributes_secrets
                ),
                env_variables_secrets=self._convert_dynamic_attributes_secrets(
                    data.env_variables_secrets
                ),
                env_variables=data.env_variables,
                created_by_user=user.full_name,
                tags=data.tags,
            )
        )
        return deployment

    async def list_deployments(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> list[Deployment]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.LIST,
            orbit_id,
        )
        return await self.__repo.list_deployments(orbit_id)

    async def get_deployment(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
    ) -> Deployment:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.READ,
            orbit_id,
        )
        deployment = await self.__repo.get_deployment(deployment_id, orbit_id)
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def request_deployment_deletion(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, deployment_id: UUID
    ) -> SatelliteQueueTask:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.DELETE,
            orbit_id,
        )
        result = await self.__repo.request_deployment_deletion(orbit_id, deployment_id)

        if not result:
            raise NotFoundError("Deployment not found")

        deployment, task = result

        if task is None:
            raise ApplicationError(
                "Deployment deletion already pending",
                409,
            )

        return task

    async def force_delete_deployment(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, deployment_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.DELETE,
            orbit_id,
        )
        dep = await self.__repo.get_deployment(deployment_id, orbit_id)

        if not dep:
            raise NotFoundError("Deployment not found")

        return await self.__repo.delete_deployment(deployment_id, orbit_id)

    async def list_worker_deployments(self, satellite_id: UUID) -> list[Deployment]:
        return await self.__repo.list_satellite_deployments(satellite_id)

    async def get_worker_deployment(
        self, satellite_id: UUID, deployment_id: UUID
    ) -> Deployment:
        deployment = await self.__repo.get_satellite_deployment(
            deployment_id, satellite_id
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def update_worker_deployment(
        self,
        satellite_id: UUID,
        deployment_id: UUID,
        data: DeploymentUpdateIn,
    ) -> Deployment:
        update_data = DeploymentUpdate.model_validate(
            {"id": deployment_id, **data.model_dump(exclude_unset=True)}
        )
        deployment = await self.__repo.update_deployment(
            deployment_id,
            satellite_id,
            update_data,
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def delete_worker_deployment(
        self, satellite_id: UUID, deployment_id: UUID
    ) -> None:
        deployment = await self.__repo.get_satellite_deployment(
            deployment_id, satellite_id
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        if deployment.status != DeploymentStatus.DELETION_PENDING:
            raise ApplicationError(
                "Incorrect deployment status. Request deployment deletion first.",
                409,
            )
        return await self.__repo.delete_satellite_deployment(
            deployment_id, satellite_id
        )

    async def update_deployment_details(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
        data: DeploymentDetailsUpdateIn,
    ) -> Deployment:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.UPDATE,
            orbit_id,
        )
        if (
            data.monitoring_mode is not None
            and data.monitoring_mode != MonitoringMode.OFF
        ):
            deployment = await self.__repo.get_deployment(deployment_id, orbit_id)
            if not deployment:
                raise NotFoundError("Deployment not found")
            if data.monitoring_mode != deployment.monitoring_mode:
                satellite = await self.__sat_repo.get_satellite(deployment.satellite_id)
                if not satellite:
                    raise NotFoundError("Satellite not found")
                self._require_present_capability(
                    satellite,
                    MONITORING_CAPABILITY,
                )

        updated = await self.__repo.update_deployment_details(
            orbit_id,
            deployment_id,
            DeploymentDetailsUpdate.model_validate(
                data.model_dump(mode="json", exclude_unset=True)
            ),
        )
        if not updated:
            raise NotFoundError("Deployment not found")
        return updated

    async def verify_user_inference_access(self, orbit_id: UUID, api_key: str) -> bool:
        user = await self.__api_key_handler.authenticate_api_key(api_key)
        if not user:
            return False
        orbit = await self.__orbit_repo.get_orbit_by_id(orbit_id)
        if not orbit:
            return False
        try:
            await self.__permissions_handler.check_permissions(
                orbit.organization_id,
                user.id,
                Resource.DEPLOYMENT,
                Action.READ,
                orbit.id,
            )
        except (NotFoundError, InsufficientPermissionsError):
            return False
        return True

    async def update_worker_deployment_status(
        self,
        satellite_id: UUID,
        deployment_id: UUID,
        status: DeploymentStatus,
    ) -> Deployment:
        deployment = await self.__repo.update_deployment(
            deployment_id,
            satellite_id,
            DeploymentUpdate(id=deployment_id, status=status),
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment
