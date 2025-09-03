import hashlib
import hmac
import secrets
from typing import Any

from fastapi import status

from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import ApplicationError, NotFoundError
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

    def _generate_api_key(self) -> str:
        return f"dfssat_{secrets.token_urlsafe(32)}"

    def _get_key_hash(self, key: str) -> str:
        return hmac.new(
            self.secret_key.encode(), key.encode(), self.algorithm
        ).hexdigest()

    async def authenticate_api_key(self, api_key: str) -> Satellite | None:
        return await self.__sat_repo.get_satellite_by_hash(self._get_key_hash(api_key))

    async def list_satellites(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        paired: bool | None = None,
    ) -> list[Satellite]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.SATELLITE, Action.LIST
        )
        return await self.__sat_repo.list_satellites(orbit_id, paired)

    async def get_satellite(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        satellite_id: int,
    ) -> Satellite:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.SATELLITE, Action.READ
        )
        satellite = await self.__sat_repo.get_satellite(satellite_id)
        if not satellite or satellite.orbit_id != orbit_id:
            raise NotFoundError("Satellite not found")
        return satellite

    async def regenerate_satellite_api_key(
        self, user_id: int, organization_id: int, orbit_id: int, satellite_id: int
    ) -> str:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.SATELLITE, Action.UPDATE
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
        user_id: int,
        organization_id: int,
        orbit_id: int,
        data: SatelliteCreateIn,
    ) -> SatelliteCreateOut:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.SATELLITE, Action.CREATE
        )

        orbit = await self.__orbit_repo.get_orbit_simple(orbit_id, organization_id)
        if not orbit:
            raise NotFoundError("Orbit not found")

        user = await self.__user_repo.get_public_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        api_key = self._generate_api_key()

        satellite, task = await self.__sat_repo.create_satellite(
            SatelliteCreate(
                orbit_id=orbit_id,
                api_key_hash=self._get_key_hash(api_key),
                name=data.name,
            ),
            {"created_by_user": user.full_name},
        )
        return SatelliteCreateOut(satellite=satellite, api_key=api_key, task=task)

    async def update_satellite(
        self,
        user_id: int,
        organization_id: int,
        orbit_id: int,
        satellite_update: SatelliteUpdate,
    ) -> Satellite:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id, orbit_id, user_id, Resource.SATELLITE, Action.UPDATE
        )

        satellite = await self.__sat_repo.get_satellite(satellite_update.id)
        if not satellite:
            raise NotFoundError("Satellite not found")

        updated_satellite = await self.__sat_repo.update_satellite(satellite_update)

        if not updated_satellite:
            raise NotFoundError("Satellite not found")

        return updated_satellite

    async def pair_satellite(
        self,
        satellite_id: int,
        base_url: str,
        capabilities: dict[SatelliteCapability, dict[str, str | int] | None],
    ) -> Satellite:
        if not capabilities:
            raise ApplicationError("Invalid capabilities", status.HTTP_400_BAD_REQUEST)

        satellite = await self.__sat_repo.get_satellite(satellite_id)
        if not satellite:
            raise NotFoundError("Satellite not found")

        if satellite.paired:
            if satellite.capabilities != capabilities:
                raise ApplicationError(
                    "Satellite already paired", status.HTTP_409_CONFLICT
                )
            return satellite

        updated_satellite = await self.__sat_repo.pair_satellite(
            satellite_id, base_url, capabilities
        )

        if not updated_satellite:
            raise NotFoundError("Satellite not found")

        return updated_satellite

    async def touch_last_seen(self, satellite_id: int) -> None:
        await self.__sat_repo.touch_last_seen(satellite_id)

    async def list_tasks(
        self, satellite_id: int, status: SatelliteTaskStatus | None = None
    ) -> list[SatelliteQueueTask]:
        return await self.__sat_repo.list_tasks(satellite_id, status)

    async def update_task_status(
        self,
        satellite_id: int,
        task_id: int,
        status: SatelliteTaskStatus,
        result: dict[str, Any] | None = None,
    ) -> SatelliteQueueTask:
        task = await self.__sat_repo.update_task_status(
            satellite_id, task_id, status, result
        )
        if not task:
            raise NotFoundError("Task not found")
        return task
