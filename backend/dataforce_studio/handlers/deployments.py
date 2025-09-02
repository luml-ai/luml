from dataforce_studio.handlers.api_keys import APIKeyHandler
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
)
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.repositories.deployments import DeploymentRepository
from dataforce_studio.repositories.model_artifacts import ModelArtifactRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.satellites import SatelliteRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentCreateIn,
    DeploymentStatus,
    DeploymentUpdate,
)
from dataforce_studio.schemas.permissions import Action, Resource


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

    async def create_deployment(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        data: DeploymentCreateIn,
    ) -> Deployment:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.CREATE,
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
                secrets=data.secrets,
                created_by_user=user.full_name,
            )
        )
        return deployment

    async def list_deployments(
        self, user_id: int, organization_id: int, orbit_id: int
    ) -> list[Deployment]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.LIST,
        )
        return await self.__repo.list_deployments(orbit_id)

    async def get_deployment(
        self, user_id: int, organization_id: int, orbit_id: int, deployment_id: int
    ) -> Deployment:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.READ,
        )
        deployment = await self.__repo.get_deployment(deployment_id, orbit_id)
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def list_worker_deployments(self, satellite_id: int) -> list[Deployment]:
        return await self.__repo.list_satellite_deployments(satellite_id)

    async def update_worker_deployment(
        self, satellite_id: int, deployment_id: int, inference_url: str
    ) -> Deployment:
        deployment = await self.__repo.update_deployment(
            deployment_id,
            satellite_id,
            DeploymentUpdate(
                id=deployment_id,
                inference_url=inference_url,
                status=DeploymentStatus.ACTIVE,
            ),
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def verify_user_inference_access(self, orbit_id: int, api_key: str) -> bool:
        user = await self.__api_key_handler.authenticate_api_key(api_key)
        if not user:
            return False
        orbit = await self.__orbit_repo.get_orbit_by_id(orbit_id)
        if not orbit:
            return False
        try:
            await self.__permissions_handler.check_orbit_action_access(
                orbit.organization_id,
                orbit.id,
                user.id,
                Resource.DEPLOYMENT,
                Action.READ,
            )
        except (NotFoundError, InsufficientPermissionsError):
            return False
        return True
