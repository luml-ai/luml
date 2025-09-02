from collections.abc import Sequence

from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    InsufficientPermissionsError,
    NotFoundError,
)
from dataforce_studio.repositories.orbits import OrbitRepository
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole
from dataforce_studio.schemas.permissions import (
    Action,
    Resource,
    orbit_permissions,
    organization_permissions,
)


class PermissionsHandler:
    __user_repository = UserRepository(engine)
    __orbits_repository = OrbitRepository(engine)
    __org_permissions = organization_permissions
    __orbit_permissions = orbit_permissions

    def has_organization_permission(
        self, role: str, resource: Resource, action: Action
    ) -> bool:
        return action in self.__org_permissions.get(OrgRole(role), {}).get(resource, [])

    def has_orbit_permission(
        self, role: str, resource: Resource, action: Action
    ) -> bool:
        return action in self.__orbit_permissions.get(OrbitRole(role), {}).get(
            resource, []
        )

    async def check_organization_permission(
        self,
        organization_id: int,
        user_id: int,
        resource: Resource,
        action: Action,
    ) -> str:
        org_member_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        if not org_member_role:
            raise NotFoundError("User is not member of the organization")

        if not self.has_organization_permission(org_member_role, resource, action):
            raise InsufficientPermissionsError()

        return org_member_role

    async def check_orbit_permission(
        self,
        orbit_id: int,
        user_id: int,
        resource: Resource,
        action: Action,
    ) -> str:
        member_role = await self.__orbits_repository.get_orbit_member_role(
            orbit_id, user_id
        )

        if not member_role:
            raise NotFoundError("User is not member of the orbit")

        if not self.has_orbit_permission(member_role, resource, action):
            raise InsufficientPermissionsError()

        return member_role

    async def check_orbit_action_access(
        self,
        organization_id: int,
        orbit_id: int,
        user_id: int,
        resource: Resource,
        action: Action,
    ) -> tuple[None, str] | tuple[str, None]:
        org_role = await self.check_organization_permission(
            organization_id,
            user_id,
            resource,
            action,
        )

        if org_role not in (OrgRole.OWNER, OrgRole.ADMIN):
            orbit_role = await self.check_orbit_permission(
                orbit_id,
                user_id,
                resource,
                action,
            )
            return None, orbit_role

        return org_role, None

    def _get_organization_permissions_for_role_and_resources(
        self,
        role: OrgRole,
        resources: Sequence[Resource],
    ) -> dict[str, list[str]]:
        all_permissions = organization_permissions.get(role, {})

        result: dict[str, list[str]] = {}
        for resource in resources:
            if resource in all_permissions:
                result[str(resource.value)] = [
                    action.value for action in all_permissions[resource]
                ]
        return result

    def get_orbit_permissions_for_role_and_resources(
        self,
        role: OrbitRole,
        resources: Sequence[Resource],
    ) -> dict[str, list[str]]:
        all_permissions = orbit_permissions.get(role, {})

        result: dict[str, list[str]] = {}
        for resource in resources:
            if resource in all_permissions:
                result[str(resource.value)] = [
                    action.value for action in all_permissions[resource]
                ]
        return result

    def get_organization_permissions_by_role(
        self, role: str | None
    ) -> dict[str, list[str]] | None:
        if not role:
            return None
        permissions = self._get_organization_permissions_for_role_and_resources(
            OrgRole(role),
            [
                Resource.ORGANIZATION,
                Resource.ORGANIZATION_USER,
                Resource.ORGANIZATION_INVITE,
                Resource.BILLING,
                Resource.ORBIT,
            ],
        )
        if Action.CREATE in permissions.get(Resource.ORBIT, []):
            permissions[Resource.ORBIT] = [Action.CREATE]
        else:
            permissions.pop(Resource.ORBIT, None)
        return permissions

    def get_orbit_permissions_by_role(
        self, org_role: str | None = None, role: str | None = None
    ) -> dict[str, list[str]]:
        if org_role and org_role in (OrgRole.OWNER, OrgRole.ADMIN):
            return self._get_organization_permissions_for_role_and_resources(
                OrgRole(org_role),
                [
                    Resource.ORBIT,
                    Resource.ORBIT_USER,
                    Resource.MODEL,
                    Resource.COLLECTION,
                    Resource.SATELLITE,
                    Resource.ORBIT_SECRET,
                    Resource.DEPLOYMENT,
                ],
            )

        if not role:
            return {}

        return self.get_orbit_permissions_for_role_and_resources(
            OrbitRole(role),
            [
                Resource.ORBIT,
                Resource.ORBIT_USER,
                Resource.MODEL,
                Resource.COLLECTION,
                Resource.SATELLITE,
                Resource.ORBIT_SECRET,
                Resource.DEPLOYMENT,
            ],
        )
