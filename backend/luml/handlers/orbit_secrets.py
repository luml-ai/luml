from uuid import UUID

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
)
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretCreateIn,
    OrbitSecretOut,
    OrbitSecretUpdate,
)
from luml.schemas.permissions import Action, Resource


class OrbitSecretHandler:
    __secret_repository = OrbitSecretRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def create_orbit_secret(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        secret: OrbitSecretCreateIn,
    ) -> OrbitSecretOut:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_SECRET,
            Action.CREATE,
            orbit_id,
        )
        secret_create = OrbitSecretCreate(**secret.model_dump(), orbit_id=orbit_id)
        try:
            created = await self.__secret_repository.create_orbit_secret(secret_create)
        except DatabaseConstraintError as error:
            raise ApplicationError(
                f"Secret with name {secret.name} already exist in orbit."
            ) from error
        return OrbitSecretOut.model_validate(created)

    async def get_orbit_secrets(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> list[OrbitSecretOut]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_SECRET,
            Action.LIST,
            orbit_id,
        )
        secrets = await self.__secret_repository.get_orbit_secrets(orbit_id)

        return [
            OrbitSecretOut(
                id=s.id,
                name=s.name,
                value="",
                tags=s.tags,
                orbit_id=s.orbit_id,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in secrets
        ]

    async def get_orbit_secret(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        secret_id: UUID,
    ) -> OrbitSecretOut:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_SECRET,
            Action.READ,
            orbit_id,
        )
        secret = await self.__secret_repository.get_orbit_secret(secret_id)
        if not secret:
            raise NotFoundError("Orbit secret not found")
        return OrbitSecretOut.model_validate(secret)

    async def update_orbit_secret(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        secret_id: UUID,
        secret: OrbitSecretUpdate,
    ) -> OrbitSecretOut:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_SECRET,
            Action.UPDATE,
            orbit_id,
        )
        updated = await self.__secret_repository.update_orbit_secret(secret_id, secret)
        if not updated:
            raise NotFoundError("Orbit secret not found")
        return OrbitSecretOut.model_validate(updated)

    async def delete_orbit_secret(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        secret_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_SECRET,
            Action.DELETE,
            orbit_id,
        )
        await self.__secret_repository.delete_orbit_secret(secret_id)

    async def get_worker_orbit_secrets(self, orbit_id: UUID) -> list[OrbitSecret]:
        return await self.__secret_repository.get_orbit_secrets(orbit_id)

    async def get_worker_orbit_secret(
        self, orbit_id: UUID, secret_id: UUID
    ) -> OrbitSecret:
        secret = await self.__secret_repository.get_orbit_secret(secret_id)
        if not secret or secret.orbit_id != orbit_id:
            raise NotFoundError("Orbit secret not found")
        return secret
