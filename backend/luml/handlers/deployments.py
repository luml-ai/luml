from uuid import UUID

from luml.handlers.api_keys import APIKeyHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.model_artifacts import ModelArtifactRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.users import UserRepository
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentCreateIn,
    DeploymentDetailsUpdate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
    DeploymentUpdate,
    DeploymentUpdateIn,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import SatelliteQueueTask


class DeploymentHandler:
    __repo = DeploymentRepository(engine)
    __sat_repo = SatelliteRepository(engine)
    __orbit_repo = OrbitRepository(engine)
    __artifact_repo = ModelArtifactRepository(engine)
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

        artifact = await self.__artifact_repo.get_model_artifact(data.model_artifact_id)
        if not artifact:
            raise NotFoundError("Model artifact not found")

        collection = await self.__collection_repo.get_collection(artifact.collection_id)
        if not collection or collection.orbit_id != orbit_id:
            raise NotFoundError("Collection not found")

        user = await self.__user_repo.get_public_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        deployment, _ = await self.__repo.create_deployment(
            DeploymentCreate(
                orbit_id=orbit_id,
                satellite_id=data.satellite_id,
                model_id=data.model_artifact_id,
                name=data.name,
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
        dep = await self.__repo.get_deployment(deployment_id)

        if not dep:
            raise NotFoundError("Deployment not found")

        return await self.__repo.delete_deployment(deployment_id)

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
        update_data = DeploymentUpdate(
            id=deployment_id,
            inference_url=data.inference_url,
            status=data.status,
            schemas=data.schemas,
            error_message=data.error_message,
            tags=data.tags,
        )
        deployment = await self.__repo.update_deployment(
            deployment_id,
            satellite_id,
            update_data,
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def delete_worker_deployment(self, deployment_id: UUID) -> None:
        deployment = await self.__repo.get_deployment(deployment_id)
        if not deployment:
            raise NotFoundError("Deployment not found")
        if deployment.status != DeploymentStatus.DELETION_PENDING:
            raise ApplicationError(
                "Incorrect deployment status. Request deployment deletion first.",
                409,
            )
        return await self.__repo.delete_deployment(deployment_id)

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
        updated = await self.__repo.update_deployment_details(
            orbit_id,
            deployment_id,
            DeploymentDetailsUpdate.model_validate(data.model_dump(mode="json")),
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
