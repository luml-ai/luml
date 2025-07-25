from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    BucketSecretInUseError,
    DatabaseConstraintError,
    NotFoundError,
)
from dataforce_studio.repositories.bucket_secrets import BucketSecretRepository
from dataforce_studio.schemas.bucket_secrets import (
    BucketSecret,
    BucketSecretCreate,
    BucketSecretCreateIn,
    BucketSecretOut,
    BucketSecretUpdate,
    BucketSecretUrls,
)
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.services.s3_service import S3Service


class BucketSecretHandler:
    __secret_repository = BucketSecretRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def _get_secret_or_raise(self, secret_id: int) -> BucketSecret:
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Bucket secret not found")
        return secret

    async def create_bucket_secret(
        self, user_id: int, organization_id: int, secret: BucketSecretCreateIn
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.CREATE
        )
        secret_create = BucketSecretCreate(
            **secret.model_dump(), organization_id=organization_id
        )
        created = await self.__secret_repository.create_bucket_secret(secret_create)
        return BucketSecretOut.model_validate(created)

    async def get_organization_bucket_secrets(
        self, user_id: int, organization_id: int
    ) -> list[BucketSecretOut]:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.LIST
        )
        secrets = await self.__secret_repository.get_organization_bucket_secrets(
            organization_id
        )
        return [BucketSecretOut.model_validate(s) for s in secrets]

    async def get_bucket_secret(
        self, user_id: int, organization_id: int, secret_id: int
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
        )
        secret = await self.__secret_repository.get_bucket_secret(secret_id)
        if not secret:
            raise NotFoundError("Secret not found")
        return BucketSecretOut.model_validate(secret)

    async def update_bucket_secret(
        self,
        user_id: int,
        organization_id: int,
        secret_id: int,
        secret: BucketSecretUpdate,
    ) -> BucketSecretOut:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.UPDATE
        )
        secret.id = secret_id
        db_secret = await self.__secret_repository.update_bucket_secret(secret)
        if not db_secret:
            raise NotFoundError("Secret not found")
        return BucketSecretOut.model_validate(db_secret)

    async def delete_bucket_secret(
        self, user_id: int, organization_id: int, secret_id: int
    ) -> None:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.DELETE
        )
        try:
            await self.__secret_repository.delete_bucket_secret(secret_id)
        except DatabaseConstraintError as e:
            raise BucketSecretInUseError() from e

    async def get_bucket_urls(
        self, organization_id: int, user_id: int, secret_id: int
    ) -> BucketSecretUrls:
        await self.__permissions_handler.check_organization_permission(
            organization_id, user_id, Resource.BUCKET_SECRET, Action.READ
        )
        object_name = "test_file"

        secret = await self._get_secret_or_raise(secret_id)

        s3_service = S3Service(secret)

        return BucketSecretUrls(
            presigned_url=await s3_service.get_presigned_url(object_name),
            download_url=await s3_service.get_download_url(object_name),
            delete_url=await s3_service.get_delete_url(object_name),
        )
