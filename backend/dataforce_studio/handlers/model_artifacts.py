from uuid import UUID, uuid4

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    BucketSecretNotFoundError,
    CollectionNotFoundError,
    InvalidStatusTransitionError,
    ModelArtifactNotFoundError,
    NotFoundError,
    OrbitNotFoundError,
    OrganizationLimitReachedError,
)
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.repositories.collections import CollectionRepository
from dataforce_studio.repositories.deployments import DeploymentRepository
from dataforce_studio.repositories.model_artifacts import ModelArtifactRepository
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.bucket_secrets import BucketSecret
from dataforce_studio.schemas.model_artifacts import (
    Collection,
    CreateModelArtifactResponse,
    ModelArtifact,
    ModelArtifactCreate,
    ModelArtifactDetails,
    ModelArtifactIn,
    ModelArtifactStatus,
    ModelArtifactUpdate,
    ModelArtifactUpdateIn,
    SatelliteModelArtifactResponse,
)
from dataforce_studio.schemas.orbit import Orbit
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.services.s3_service import S3Service


class ModelArtifactHandler:
    __repository = ModelArtifactRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __secret_repository = BucketSecretRepository(engine)
    __collection_repository = CollectionRepository(engine)
    __deployment_repository = DeploymentRepository(engine)
    __user_repository = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    __model_artifact_transitions = {
        ModelArtifactStatus.PENDING_UPLOAD: {
            ModelArtifactStatus.UPLOADED,
            ModelArtifactStatus.UPLOAD_FAILED,
        },
        ModelArtifactStatus.PENDING_DELETION: {ModelArtifactStatus.DELETION_FAILED},
    }

    async def _get_secret_or_raise(self, secret_id: UUID) -> BucketSecret:
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise BucketSecretNotFoundError()
        return secret

    async def _get_s3_service(self, secret_id: UUID) -> S3Service:
        secret = await self._get_secret_or_raise(secret_id)
        return S3Service(secret)

    async def _check_orbit_and_collection_access(
        self, organization_id: UUID, orbit_id: UUID, collection_id: UUID
    ) -> tuple[Orbit, Collection]:
        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit or orbit.organization_id != organization_id:
            raise OrbitNotFoundError()
        collection = await self.__collection_repository.get_collection(collection_id)
        if not collection or collection.orbit_id != orbit_id:
            raise CollectionNotFoundError()
        return orbit, collection

    async def _model_artifact_deletion_checks(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
    ) -> ModelArtifactDetails:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.DELETE,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        model_artifact = await self.__repository.get_model_artifact_details(
            model_artifact_id
        )

        if not model_artifact:
            raise ModelArtifactNotFoundError()

        return model_artifact

    async def _check_organization_models_limit(self, organization_id: UUID) -> None:
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")

        if organization.total_model_artifacts >= organization.model_artifacts_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of model artifacts"
            )

    async def create_model_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact: ModelArtifactIn,
    ) -> CreateModelArtifactResponse:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.CREATE,
            orbit_id,
        )

        orbit, collection = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        await self._check_organization_models_limit(organization_id)

        user = await self.__user_repository.get_public_user_by_id(user_id)

        if not user:
            raise NotFoundError("User not found")

        unique_id = uuid4().hex
        object_name = f"{unique_id}-{model_artifact.file_name}"

        bucket_location = f"orbit-{orbit_id}/collection-{collection_id}/{object_name}"

        created_model_artifact = await self.__repository.create_model_artifact(
            ModelArtifactCreate(
                collection_id=collection_id,
                file_name=model_artifact.file_name,
                model_name=model_artifact.model_name,
                description=model_artifact.description,
                metrics=model_artifact.metrics,
                manifest=model_artifact.manifest,
                file_hash=model_artifact.file_hash,
                file_index=model_artifact.file_index,
                bucket_location=bucket_location,
                size=model_artifact.size,
                unique_identifier=unique_id,
                tags=model_artifact.tags,
                status=ModelArtifactStatus.PENDING_UPLOAD,
                created_by_user=user.full_name,
            )
        )

        s3_service = await self._get_s3_service(orbit.bucket_secret_id)

        upload_data = await s3_service.create_upload(
            bucket_location, model_artifact.size
        )

        return CreateModelArtifactResponse(
            model=created_model_artifact, upload_details=upload_data
        )

    async def update_model_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
        model_artifact: ModelArtifactUpdateIn,
    ) -> ModelArtifact:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.UPDATE,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        model_artifact_obj = await self.__repository.get_model_artifact(
            model_artifact_id
        )

        if not model_artifact_obj:
            raise ModelArtifactNotFoundError()

        if (
            model_artifact.status
            and model_artifact.status
            not in self.__model_artifact_transitions.get(
                model_artifact_obj.status, set()
            )
        ):
            raise InvalidStatusTransitionError(
                f"Invalid status transition from "
                f"{model_artifact_obj.status} to {model_artifact.status}"
            )

        update_data = model_artifact.model_dump(exclude_unset=True)
        update_data["id"] = model_artifact_id
        updated = await self.__repository.update_model_artifact(
            model_artifact_id,
            collection_id,
            ModelArtifactUpdate(**update_data),
        )

        if not updated:
            raise ModelArtifactNotFoundError()

        return updated

    async def request_download_url(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
    ) -> str:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.READ,
            orbit_id,
        )

        orbit, collection = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model_artifact = await self.__repository.get_model_artifact(model_artifact_id)
        if not model_artifact:
            raise ModelArtifactNotFoundError()

        s3_service = await self._get_s3_service(orbit.bucket_secret_id)
        return await s3_service.get_download_url(model_artifact.bucket_location)

    async def request_delete_url(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
    ) -> str:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.DELETE,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model_artifact = await self.__repository.get_model_artifact_details(
            model_artifact_id
        )
        if not model_artifact:
            raise ModelArtifactNotFoundError()

        if model_artifact.deployments:
            raise ApplicationError(
                "Cannot delete model artifact because it is used in deployments.", 409
            )

        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit:
            raise OrbitNotFoundError()

        s3_service = await self._get_s3_service(orbit.bucket_secret_id)
        url = await s3_service.get_delete_url(model_artifact.bucket_location)
        await self.__repository.update_status(
            model_artifact_id, ModelArtifactStatus.PENDING_DELETION
        )
        return url

    async def request_satellite_download_url(
        self,
        orbit_id: UUID,
        model_artifact_id: UUID,
    ) -> str:
        model_artifact = await self.__repository.get_model_artifact(model_artifact_id)
        if not model_artifact:
            raise ModelArtifactNotFoundError()

        collection = await self.__collection_repository.get_collection(
            model_artifact.collection_id
        )
        if not collection or collection.orbit_id != orbit_id:
            raise ModelArtifactNotFoundError()

        orbit = await self.__orbit_repository.get_orbit_by_id(orbit_id)
        if not orbit:
            raise OrbitNotFoundError()

        s3_service = await self._get_s3_service(orbit.bucket_secret_id)
        return await s3_service.get_download_url(model_artifact.bucket_location)

    async def confirm_deletion(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
    ) -> None:
        model_artifact = await self._model_artifact_deletion_checks(
            user_id, organization_id, orbit_id, collection_id, model_artifact_id
        )

        if model_artifact.status != ModelArtifactStatus.PENDING_DELETION:
            raise InvalidStatusTransitionError(
                f"Unable to confirm deletion with status '{model_artifact.status}'"
            )
        await self.__repository.delete_model_artifact(model_artifact_id)

    async def force_delete_model_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
    ) -> None:
        model_artifact = await self._model_artifact_deletion_checks(
            user_id, organization_id, orbit_id, collection_id, model_artifact_id
        )

        if model_artifact.deployments:
            await self.__deployment_repository.delete_deployments_by_model_id(
                model_artifact_id
            )

        await self.__repository.delete_model_artifact(model_artifact_id)

    async def get_collection_model_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
    ) -> list[ModelArtifact]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.LIST,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        return await self.__repository.get_collection_model_artifact(collection_id)

    async def get_model_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        model_artifact_id: UUID,
    ) -> tuple[ModelArtifact, str]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.MODEL,
            Action.READ,
            orbit_id,
        )
        orbit, _ = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        model_artifact = await self.__repository.get_model_artifact(model_artifact_id)
        if not model_artifact:
            raise ModelArtifactNotFoundError()

        s3_service = await self._get_s3_service(orbit.bucket_secret_id)
        url = await s3_service.get_download_url(model_artifact.bucket_location)
        return model_artifact, url

    async def get_satellite_model_artifact(
        self,
        orbit_id: UUID,
        model_artifact_id: UUID,
    ) -> SatelliteModelArtifactResponse:
        model_artifact = await self.__repository.get_model_artifact(model_artifact_id)
        if not model_artifact:
            raise ModelArtifactNotFoundError()

        orbit = await self.__orbit_repository.get_orbit_by_id(orbit_id)
        if not orbit:
            raise OrbitNotFoundError()

        s3_service = await self._get_s3_service(orbit.bucket_secret_id)
        url = await s3_service.get_download_url(model_artifact.bucket_location)
        return SatelliteModelArtifactResponse(model=model_artifact, url=url)
