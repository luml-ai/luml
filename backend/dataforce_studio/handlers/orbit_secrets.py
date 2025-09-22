from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import NotFoundError
from dataforce_studio.repositories.orbit_secrets import OrbitSecretRepository
from dataforce_studio.schemas.orbit_secret import (
    OrbitSecret,
    OrbitSecretCreate,
    OrbitSecretCreateIn,
    OrbitSecretOut,
    OrbitSecretUpdate,
)
from dataforce_studio.schemas.permissions import Action, Resource


class OrbitSecretHandler:
    __secret_repository = OrbitSecretRepository(engine)
    __permissions_handler = PermissionsHandler()

    async def create_orbit_secret(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        secret: OrbitSecretCreateIn,
    ) -> OrbitSecretOut:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.CREATE
        )
        secret_create = OrbitSecretCreate(**secret.model_dump(), orbit_id=orbit_id)
        created = await self.__secret_repository.create_orbit_secret(secret_create)
        return OrbitSecretOut.model_validate(created)

    async def get_orbit_secrets(
        self, user_id: int, organization_id: int, orbit_id: int
    ) -> list[OrbitSecretOut]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.LIST
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
        self, user_id: int, organization_id: int, orbit_id: int, secret_id: int
    ) -> OrbitSecretOut:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.READ
        )
        secret = await self.__secret_repository.get_orbit_secret(secret_id)
        if not secret:
            raise NotFoundError("Orbit secret not found")
        return OrbitSecretOut.model_validate(secret)

    async def update_orbit_secret(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        secret_id: int,
        secret: OrbitSecretUpdate,
    ) -> OrbitSecretOut:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.UPDATE
        )
        updated = await self.__secret_repository.update_orbit_secret(secret_id, secret)
        if not updated:
            raise NotFoundError("Orbit secret not found")
        return OrbitSecretOut.model_validate(updated)

    async def delete_orbit_secret(
        self, user_id: int, organization_id: int, orbit_id: int, secret_id: int
    ) -> None:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.ORBIT_SECRET, Action.DELETE
        )
        await self.__secret_repository.delete_orbit_secret(secret_id)

    async def get_worker_orbit_secrets(self, orbit_id: int) -> list[OrbitSecret]:
        return await self.__secret_repository.get_orbit_secrets(orbit_id)

    async def get_worker_orbit_secret(
        self, orbit_id: int, secret_id: int
    ) -> OrbitSecret:
        secret = await self.__secret_repository.get_orbit_secret(secret_id)
        if not secret or secret.orbit_id != orbit_id:
            raise NotFoundError("Orbit secret not found")
        return secret
