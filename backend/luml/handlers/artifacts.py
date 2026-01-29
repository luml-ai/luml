from uuid import UUID, uuid4

from luml.clients.base_storage_client import BaseStorageClient
from luml.clients.storage_factory import create_storage_client
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactNotFoundError,
    ArtifactTypeMismatchError,
    BucketSecretNotFoundError,
    CollectionNotFoundError,
    InvalidSortingError,
    InvalidStatusTransitionError,
    NotFoundError,
    OrbitNotFoundError,
    OrganizationLimitReachedError,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreate,
    ArtifactDetails,
    ArtifactIn,
    ArtifactsList,
    ArtifactSortBy,
    ArtifactStatus,
    ArtifactType,
    ArtifactUpdate,
    ArtifactUpdateIn,
    CreateArtifactResponse,
    SatelliteArtifactResponse, LumlArtifactManifest,
)
from luml.schemas.bucket_secrets import BucketSecret
from luml.schemas.collections import Collection, is_artifact_type_allowed
from luml.schemas.general import PaginationParams, SortOrder
from luml.schemas.orbit import Orbit
from luml.schemas.permissions import Action, Resource
from luml.utils.pagination import decode_cursor, get_cursor


class ArtifactHandler:
    __repository = ArtifactRepository(engine)
    __orbit_repository = OrbitRepository(engine)
    __secret_repository = BucketSecretRepository(engine)
    __collection_repository = CollectionRepository(engine)
    __deployment_repository = DeploymentRepository(engine)
    __user_repository = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    __artifact_transitions = {
        ArtifactStatus.PENDING_UPLOAD: {
            ArtifactStatus.UPLOADED,
            ArtifactStatus.UPLOAD_FAILED,
        },
        ArtifactStatus.PENDING_DELETION: {ArtifactStatus.DELETION_FAILED},
    }

    async def _get_secret_or_raise(self, secret_id: UUID) -> BucketSecret:
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise BucketSecretNotFoundError()
        return secret

    async def _get_storage_client(self, secret_id: UUID) -> BaseStorageClient:
        secret = await self._get_secret_or_raise(secret_id)
        return create_storage_client(secret.type)(secret)  # type: ignore[arg-type]

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

    async def _artifact_deletion_checks(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
    ) -> ArtifactDetails:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.DELETE,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        artifact = await self.__repository.get_artifact_details(artifact_id)

        if not artifact:
            raise ArtifactNotFoundError()

        return artifact

    async def _check_organization_artifacts_limit(self, organization_id: UUID) -> None:
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")

        if organization.total_artifacts >= organization.artifacts_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of artifacts"
            )

    async def _is_metric_sort(self, collection_id: UUID, sort_by: str) -> bool:
        if sort_by == "extra_values":
            raise InvalidSortingError(
                "Cannot sort by 'extra_values'. Pass a metric key"
            )

        if sort_by in ArtifactSortBy._value2member_map_:
            return False

        extra_values = await self.__repository.get_collection_artifacts_extra_values(
            collection_id
        )
        if sort_by not in extra_values:
            raise InvalidSortingError(f"Invalid sorting column: {sort_by}")
        return True

    @staticmethod
    def _define_artifact_type(artifact) -> ArtifactType:
        structure = artifact.file_index.keys()
        model_structure_files = [
            "dtypes.json"
            "env.json"
            "manifest.json"
            "meta.json"
            "ops.json"
            "variant_config.json"
        ]

        try:
            if isinstance(artifact.manifest, LumlArtifactManifest):
                return ArtifactType(artifact.manifest.type)
        except Exception:
            raise ArtifactTypeMismatchError("Unsupported LUML Artifact type.")

        if all(file in structure for file in model_structure_files):
            return ArtifactType.MODEL

        raise ArtifactTypeMismatchError("Could not define artifact type.")

    async def create_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact: ArtifactIn,
    ) -> CreateArtifactResponse:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.CREATE,
            orbit_id,
        )

        orbit, collection = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        artifact_type = self._define_artifact_type(artifact)

        if not is_artifact_type_allowed(collection.collection_type, artifact_type):
            raise ArtifactTypeMismatchError()

        await self._check_organization_artifacts_limit(organization_id)

        user = await self.__user_repository.get_public_user_by_id(user_id)

        if not user:
            raise NotFoundError("User not found")

        unique_id = uuid4().hex
        object_name = f"{unique_id}-{artifact.file_name}"

        bucket_location = f"orbit-{orbit_id}/collection-{collection_id}/{object_name}"

        created_artifact = await self.__repository.create_artifact(
            ArtifactCreate(
                collection_id=collection_id,
                file_name=artifact.file_name,
                name=artifact.name,
                description=artifact.description,
                extra_values=artifact.extra_values,
                manifest=artifact.manifest,
                file_hash=artifact.file_hash,
                file_index=artifact.file_index,
                bucket_location=bucket_location,
                size=artifact.size,
                unique_identifier=unique_id,
                tags=artifact.tags,
                status=ArtifactStatus.PENDING_UPLOAD,
                created_by_user=user.full_name,
                type=artifact_type,
            )
        )

        storage_service = await self._get_storage_client(orbit.bucket_secret_id)

        upload_data = await storage_service.create_upload(
            bucket_location, artifact.size
        )

        return CreateArtifactResponse(
            artifact=created_artifact, upload_details=upload_data
        )

    async def update_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
        artifact: ArtifactUpdateIn,
    ) -> Artifact:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.UPDATE,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        artifact_obj = await self.__repository.get_artifact(artifact_id)

        if not artifact_obj:
            raise ArtifactNotFoundError()

        if artifact.status and artifact.status not in self.__artifact_transitions.get(
            artifact_obj.status, set()
        ):
            raise InvalidStatusTransitionError(
                f"Invalid status transition from "
                f"{artifact_obj.status} to {artifact.status}"
            )

        update_data = artifact.model_dump(exclude_unset=True)
        update_data["id"] = artifact_id
        updated = await self.__repository.update_artifact(
            artifact_id,
            collection_id,
            ArtifactUpdate(**update_data),
        )

        if not updated:
            raise ArtifactNotFoundError()

        return updated

    async def request_download_url(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
    ) -> str:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.READ,
            orbit_id,
        )

        orbit, collection = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        artifact = await self.__repository.get_artifact(artifact_id)
        if not artifact:
            raise ArtifactNotFoundError()

        storage_service = await self._get_storage_client(orbit.bucket_secret_id)
        return await storage_service.get_download_url(artifact.bucket_location)

    async def request_delete_url(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
    ) -> str:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.DELETE,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        artifact = await self.__repository.get_artifact_details(artifact_id)
        if not artifact:
            raise ArtifactNotFoundError()

        if artifact.deployments:
            raise ApplicationError(
                "Cannot delete artifact because it is used in deployments.", 409
            )

        orbit = await self.__orbit_repository.get_orbit_simple(
            orbit_id, organization_id
        )
        if not orbit:
            raise OrbitNotFoundError()

        storage_service = await self._get_storage_client(orbit.bucket_secret_id)
        url = await storage_service.get_delete_url(artifact.bucket_location)
        await self.__repository.update_status(
            artifact_id, ArtifactStatus.PENDING_DELETION
        )
        return url

    async def request_satellite_download_url(
        self,
        orbit_id: UUID,
        artifact_id: UUID,
    ) -> str:
        artifact = await self.__repository.get_artifact(artifact_id)
        if not artifact:
            raise ArtifactNotFoundError()

        collection = await self.__collection_repository.get_collection(
            artifact.collection_id
        )
        if not collection or collection.orbit_id != orbit_id:
            raise ArtifactNotFoundError()

        orbit = await self.__orbit_repository.get_orbit_by_id(orbit_id)
        if not orbit:
            raise OrbitNotFoundError()

        storage_service = await self._get_storage_client(orbit.bucket_secret_id)
        return await storage_service.get_download_url(artifact.bucket_location)

    async def confirm_deletion(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
    ) -> None:
        artifact = await self._artifact_deletion_checks(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

        if artifact.status != ArtifactStatus.PENDING_DELETION:
            raise InvalidStatusTransitionError(
                f"Unable to confirm deletion with status '{artifact.status}'"
            )
        await self.__repository.delete_artifact(artifact_id)

    async def force_delete_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
    ) -> None:
        artifact = await self._artifact_deletion_checks(
            user_id, organization_id, orbit_id, collection_id, artifact_id
        )

        if artifact.deployments:
            await self.__deployment_repository.delete_deployments_by_artifact_id(
                artifact_id
            )

        await self.__repository.delete_artifact(artifact_id)

    async def get_collection_artifacts(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        cursor_str: str | None = None,
        limit: int = 100,
        sort_by: str = "created_at",
        order: SortOrder = SortOrder.DESC,
    ) -> ArtifactsList:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.LIST,
            orbit_id,
        )
        await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )

        is_metric = await self._is_metric_sort(collection_id, sort_by)
        cursor = decode_cursor(cursor_str)

        repo_sort_by = "extra_values" if is_metric else sort_by
        extra_sort_field = sort_by if is_metric else None

        use_cursor = cursor if cursor and cursor.sort_by == sort_by else None

        pagination = PaginationParams(
            cursor=use_cursor,
            sort_by=repo_sort_by,
            order=order,
            limit=limit,
            extra_sort_field=extra_sort_field,
        )

        items = await self.__repository.get_collection_artifacts(
            collection_id, pagination
        )

        return ArtifactsList(
            items=items[:limit],
            cursor=get_cursor(items, limit, sort_by, is_metric),
        )

    async def get_artifact(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        collection_id: UUID,
        artifact_id: UUID,
    ) -> Artifact:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ARTIFACT,
            Action.READ,
            orbit_id,
        )
        orbit, _ = await self._check_orbit_and_collection_access(
            organization_id, orbit_id, collection_id
        )
        artifact = await self.__repository.get_artifact(artifact_id)
        if not artifact or artifact.collection_id != collection_id:
            raise NotFoundError("Artifact not found")
        return artifact

    async def get_satellite_artifact(
        self,
        orbit_id: UUID,
        artifact_id: UUID,
    ) -> SatelliteArtifactResponse:
        artifact = await self.__repository.get_artifact(artifact_id)
        if not artifact:
            raise ArtifactNotFoundError()

        orbit = await self.__orbit_repository.get_orbit_by_id(orbit_id)
        if not orbit:
            raise OrbitNotFoundError()

        storage_service = await self._get_storage_client(orbit.bucket_secret_id)
        url = await storage_service.get_download_url(artifact.bucket_location)
        return SatelliteArtifactResponse(artifact=artifact, url=url)
