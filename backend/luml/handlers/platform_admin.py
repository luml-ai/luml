import logging
from uuid import UUID

from luml.infra.db import engine
from luml.infra.exceptions import NotFoundError
from luml.repositories.platform_admin import PlatformAdminRepository
from luml.schemas.platform_admin import (
    OrganizationLimitsUpdate,
    PlatformAdmin,
    PlatformAdminOrganizationDetails,
    PlatformAdminOrganizationsPage,
    PlatformAdminUserDetails,
    PlatformAdminUsersPage,
    PlatformAdminUserUpdate,
    PlatformStats,
)

PLATFORM_ADMIN_LOGGER = "luml.platform_admin"

audit_logger = logging.getLogger(f"{PLATFORM_ADMIN_LOGGER}.audit")


def configure_platform_admin_logging() -> None:
    # The app configures no logging, so without a handler of its own the
    # INFO-level audit trail would be silently dropped.
    platform_logger = logging.getLogger(PLATFORM_ADMIN_LOGGER)
    if platform_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    platform_logger.addHandler(handler)
    platform_logger.setLevel(logging.INFO)
    platform_logger.propagate = False


class PlatformAdminHandler:
    __repository = PlatformAdminRepository(engine)

    async def get_stats(self) -> PlatformStats:
        return await self.__repository.get_stats()

    async def search_users(
        self, search: str | None, limit: int, offset: int
    ) -> PlatformAdminUsersPage:
        return await self.__repository.search_users(search, limit, offset)

    async def get_user(self, user_id: UUID) -> PlatformAdminUserDetails:
        user = await self.__repository.get_user_details(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def update_user(
        self, admin: PlatformAdmin, user_id: UUID, update: PlatformAdminUserUpdate
    ) -> PlatformAdminUserDetails:
        user = await self.__repository.update_user(user_id, update)
        if user is None:
            raise NotFoundError("User not found")
        self._audit(admin, "user.update", user_id, update.model_dump(exclude_none=True))
        return user

    async def search_organizations(
        self, search: str | None, limit: int, offset: int
    ) -> PlatformAdminOrganizationsPage:
        return await self.__repository.search_organizations(search, limit, offset)

    async def get_organization(
        self, organization_id: UUID
    ) -> PlatformAdminOrganizationDetails:
        organization = await self.__repository.get_organization_details(organization_id)
        if organization is None:
            raise NotFoundError("Organization not found")
        return organization

    async def update_organization_limits(
        self,
        admin: PlatformAdmin,
        organization_id: UUID,
        limits: OrganizationLimitsUpdate,
    ) -> PlatformAdminOrganizationDetails:
        organization = await self.__repository.update_organization_limits(
            organization_id, limits
        )
        if organization is None:
            raise NotFoundError("Organization not found")
        self._audit(
            admin,
            "organization.limits.update",
            organization_id,
            limits.model_dump(exclude_none=True),
        )
        return organization

    @staticmethod
    def _audit(
        admin: PlatformAdmin, action: str, target_id: UUID, changes: dict[str, object]
    ) -> None:
        audit_logger.info(
            "platform_admin action=%s target=%s admin=%s via=%s changes=%s",
            action,
            target_id,
            admin.email,
            admin.auth_method,
            changes,
        )
