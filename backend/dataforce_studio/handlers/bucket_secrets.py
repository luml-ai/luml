from uuid import UUID

from dataforce_studio.clients.storage_factory import create_storage_client
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    BucketSecretInUseError,
    DatabaseConstraintError,
    NotFoundError,
)
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.schemas.bucket_secrets import (
    AzureBucketSecretCreate,
    BucketSecret,
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUrls,
    S3BucketSecretCreate,
    S3BucketSecretCreateIn,
    validate_bucket_secret_out,
)
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.schemas.storage import (
    AzureMultiPartUploadDetails,
    BucketMultipartUpload,
    S3MultiPartUploadDetails,
)


class BucketSecretHandler:
    __secret_repository = BucketSecretRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def create_bucket_secret(
        self,
        user_id: UUID,
        organization_id: UUID,
        secret: BucketSecretCreateIn,
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
        )
        if isinstance(secret, S3BucketSecretCreateIn):
            secret_create: S3BucketSecretCreate | AzureBucketSecretCreate = (
                S3BucketSecretCreate(
                    **secret.model_dump(), organization_id=organization_id
                )
            )
        else:
            secret_create = AzureBucketSecretCreate(
                **secret.model_dump(), organization_id=organization_id
            )
        try:
            created = await self.__secret_repository.create_bucket_secret(secret_create)
            return validate_bucket_secret_out(created)
        except DatabaseConstraintError as error:
            raise ApplicationError(
                "Bucket secret with the given bucket name and endpoint already exists.",
                409,
            ) from error

    async def get_organization_bucket_secrets(
        self, user_id: UUID, organization_id: UUID
    ) -> list[BucketSecretOut]:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
        )
        secrets = await self.__secret_repository.get_organization_bucket_secrets(
            organization_id
        )
        return [validate_bucket_secret_out(s) for s in secrets]

    async def get_bucket_secret(
        self, user_id: UUID, organization_id: UUID, secret_id: UUID
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
        )
        secret = await self.__secret_repository.get_bucket_secret(secret_id)

        if not secret:
            raise NotFoundError("Secret not found")

        return validate_bucket_secret_out(secret)

    async def update_bucket_secret(
        self,
        user_id: UUID,
        organization_id: UUID,
        secret_id: UUID,
        secret: BucketSecretUpdate,
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
        )

        secret.id = secret_id

        try:
            db_secret = await self.__secret_repository.update_bucket_secret(secret)
        except DatabaseConstraintError as error:
            raise ApplicationError(
                "Bucket secret with the given bucket name and endpoint already exists.",
                409,
            ) from error

        if not db_secret:
            raise NotFoundError("Secret not found")

        return validate_bucket_secret_out(db_secret)

    async def delete_bucket_secret(
        self, user_id: UUID, organization_id: UUID, secret_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
        )
        try:
            await self.__secret_repository.delete_bucket_secret(secret_id)
        except DatabaseConstraintError as e:
            raise BucketSecretInUseError() from e

    async def get_bucket_urls(self, secret: BucketSecretCreateIn) -> BucketSecretUrls:
        return await self.generate_bucket_urls(secret)

    @staticmethod
    async def generate_bucket_urls(
        secret_data: BucketSecretCreateIn | BucketSecret,
    ) -> BucketSecretUrls:
        object_name = "test_file"
        storage_service = create_storage_client(secret_data.type)(secret_data)  # type: ignore[arg-type]

        return BucketSecretUrls(
            presigned_url=await storage_service.get_upload_url(object_name),
            download_url=await storage_service.get_download_url(object_name),
            delete_url=await storage_service.get_delete_url(object_name),
        )

    async def get_existing_bucket_urls(
        self, secret: BucketSecretUpdate
    ) -> BucketSecretUrls:
        original_secret = await self.__secret_repository.get_bucket_secret(secret.id)

        if not original_secret:
            raise NotFoundError("Secret not found")

        if original_secret.type != secret.type:
            raise ApplicationError("Bucket type cannot be changed", 400)

        updated_secret = original_secret.model_copy(
            update=secret.model_dump(exclude_unset=True, exclude={"id"})
        )

        return await self.generate_bucket_urls(updated_secret)

    async def get_bucket_multipart_urls(
        self, data: BucketMultipartUpload
    ) -> S3MultiPartUploadDetails | AzureMultiPartUploadDetails:
        secret = await self.__secret_repository.get_bucket_secret(data.bucket_id)

        if not secret:
            raise NotFoundError("Secret not found")

        storage_service = create_storage_client(secret.type)(secret)  # type: ignore[arg-type]

        return await storage_service.create_multipart_upload(
            data.bucket_location, data.size, data.upload_id
        )
