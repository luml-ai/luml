import hashlib
import hmac
import secrets
from typing import Any
from uuid import UUID

from fastapi import status

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.satellites import SatelliteRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.permissions import Action, Resource
from dataforce_studio.schemas.satellite import (
    Satellite,
    SatelliteCapability,
    SatelliteCreate,
    SatelliteCreateIn,
    SatelliteCreateOut,
    SatelliteQueueTask,
    SatelliteRegenerateApiKey,
    SatelliteTaskStatus,
    SatelliteUpdate,
    SatelliteUpdateIn,
)
from dataforce_studio.settings import config


class SatelliteHandler:
    __sat_repo = SatelliteRepository(engine)
    __orbit_repo = OrbitRepository(engine)
    __user_repo = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    def __init__(
        self,
        secret_key: str = config.AUTH_SECRET_KEY,
        algorithm: Any = hashlib.sha256,  # noqa: ANN401
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm

    @staticmethod
    def _generate_api_key() -> str:
        return f"dfssat_{secrets.token_urlsafe(32)}"

    def _get_key_hash(self, key: str) -> str:
        return hmac.new(
            self.secret_key.encode(), key.encode(), self.algorithm
        ).hexdigest()

    async def _check_organization_satellites_limit(self, organization_id: UUID) -> None:
        organization = await self.__user_repo.get_organization_details(organization_id)
        if not organization:
            raise NotFoundError("Organization not found")

        if organization.total_satellites >= organization.satellites_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of satellites"
            )

    async def authenticate_api_key(self, api_key: str) -> Satellite | None:
        return await self.__sat_repo.get_satellite_by_hash(self._get_key_hash(api_key))

    async def list_satellites(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        paired: bool | None = None,
    ) -> list[Satellite]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.SATELLITE,
            Action.LIST,
            orbit_id,
        )
        return await self.__sat_repo.list_satellites(orbit_id, paired)

    async def get_satellite(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        satellite_id: UUID,
    ) -> Satellite:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.SATELLITE,
            Action.READ,
            orbit_id,
        )
        satellite = await self.__sat_repo.get_satellite(satellite_id)
        if not satellite or satellite.orbit_id != orbit_id:
            raise NotFoundError("Satellite not found")
        return satellite

    async def regenerate_satellite_api_key(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        satellite_id: UUID,
    ) -> str:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.SATELLITE,
            Action.UPDATE,
            orbit_id,
        )

        satellite = await self.__sat_repo.get_satellite(satellite_id)
        if not satellite:
            raise NotFoundError("Satellite not found")

        api_key = self._generate_api_key()

        await self.__sat_repo.update_satellite(
            SatelliteRegenerateApiKey(
                id=satellite_id,
                api_key_hash=self._get_key_hash(api_key),
            )
        )
        return api_key

    async def create_satellite(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        data: SatelliteCreateIn,
    ) -> SatelliteCreateOut:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.SATELLITE,
            Action.CREATE,
            orbit_id,
        )

        await self._check_organization_satellites_limit(organization_id)

        orbit = await self.__orbit_repo.get_orbit_simple(orbit_id, organization_id)
        if not orbit:
            raise NotFoundError("Orbit not found")

        user = await self.__user_repo.get_public_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        api_key = self._generate_api_key()

        satellite = await self.__sat_repo.create_satellite(
            SatelliteCreate(
                orbit_id=orbit_id,
                api_key_hash=self._get_key_hash(api_key),
                name=data.name,
                description=data.description,
            )
        )
        return SatelliteCreateOut(satellite=satellite, api_key=api_key)

    async def update_satellite(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        satellite_id: UUID,
        satellite_update_in: SatelliteUpdateIn,
    ) -> Satellite:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.SATELLITE,
            Action.UPDATE,
            orbit_id,
        )

        satellite = await self.__sat_repo.get_satellite(satellite_id)
        if not satellite:
            raise NotFoundError("Satellite not found")

        updated_satellite = await self.__sat_repo.update_satellite(
            SatelliteUpdate(
                id=satellite_id,
                name=satellite_update_in.name,
                description=satellite_update_in.description,
            )
        )

        if not updated_satellite:
            raise NotFoundError("Satellite not found")

        return updated_satellite

    async def pair_satellite(
        self,
        satellite_id: UUID,
        base_url: str,
        capabilities: dict[SatelliteCapability, dict[str, str | int] | None],
    ) -> Satellite:
        if not capabilities:
            raise ApplicationError("Invalid capabilities", status.HTTP_400_BAD_REQUEST)

        satellite = await self.__sat_repo.get_satellite(satellite_id)
        if not satellite:
            raise NotFoundError("Satellite not found")

        if satellite.paired:
            return satellite

        updated_satellite = await self.__sat_repo.pair_satellite(
            satellite_id, base_url, capabilities
        )

        if not updated_satellite:
            raise NotFoundError("Satellite not found")

        return updated_satellite

    async def touch_last_seen(self, satellite_id: UUID) -> None:
        await self.__sat_repo.touch_last_seen(satellite_id)

    async def list_tasks(
        self, satellite_id: UUID, status: SatelliteTaskStatus | None = None
    ) -> list[SatelliteQueueTask]:
        return await self.__sat_repo.list_tasks(satellite_id, status)

    async def update_task_status(
        self,
        satellite_id: UUID,
        task_id: UUID,
        status: SatelliteTaskStatus,
        result: dict[str, Any] | None = None,
    ) -> SatelliteQueueTask:
        task = await self.__sat_repo.update_task_status(
            satellite_id, task_id, status, result
        )
        if not task:
            raise NotFoundError("Task not found")
        return task

    async def delete_satellite(
        self,
        organization_id: UUID,
        orbit_id: UUID,
        user_id: UUID,
        satellite_id: UUID,
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.SATELLITE,
            Action.DELETE,
            orbit_id,
        )

        satellite = await self.__sat_repo.get_satellite(satellite_id)

        if not satellite:
            raise NotFoundError("Satellite not found")
        try:
            return await self.__sat_repo.delete_satellite(satellite_id)
        except DatabaseConstraintError as e:
            raise ApplicationError(e.message, 409) from e
