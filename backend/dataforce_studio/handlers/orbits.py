from fastapi import BackgroundTasks

from dataforce_studio.handlers.emails import EmailHandler
from dataforce_studio.handlers.permissions import PermissionsHandler
from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    DatabaseConstraintError,
    NotFoundError,
    OrbitAccessDeniedError,
    OrbitError,
    OrbitMemberAlreadyExistsError,
    OrbitMemberNotAllowedError,
    OrbitMemberNotFoundError,
    OrbitNotFoundError,
    OrganizationLimitReachedError,
)
from dataforce_studio.repositories import (
    BucketSecretRepository,
    OrbitRepository,
    UserRepository,
)
from dataforce_studio.schemas import (
    Action,
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitMemberCreateSimple,
    OrbitUpdate,
    OrgRole,
    Resource,
    UpdateOrbitMember,
)
from dataforce_studio.settings import config


class OrbitHandler:
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)
    __orbits_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()
    __secret_repository = BucketSecretRepository(engine)

    def notify_members(
        self, orbit: OrbitDetails, background_tasks: BackgroundTasks
    ) -> None:
        if orbit.members:
            for member in orbit.members:
                background_tasks.add_task(
                    self.__email_handler.send_added_to_orbit_email,
                    member.user.full_name or "",
                    member.user.email or "",
                    orbit.name or "",
                    config.APP_EMAIL_URL,
                )

    def _set_user_orbits_permissions(self, orbits: list[Orbit]) -> list[Orbit]:
        for orbit in orbits:
            orbit.permissions = (
                self.__permissions_handler.get_orbit_permissions_by_role(
                    role=orbit.role
                )
            )
        return orbits

    def _set_orbits_permissions(
        self, orbits: list[Orbit], org_role: str
    ) -> list[Orbit]:
        for orbit in orbits:
            orbit.permissions = (
                self.__permissions_handler.get_orbit_permissions_by_role(org_role)
            )
        return orbits

    async def _check_organization_orbits_limit(
        self, organization_id: str
    ) -> None:
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")

        if organization.total_orbits >= organization.orbits_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of orbits"
            )

    async def _validate_orbit_members(
        self,
        user_id: str,
        organization_id: str,
        members: list[OrbitMemberCreate] | list[OrbitMemberCreateSimple],
    ) -> None:
        user_ids = [m.user_id for m in members]

        if len(user_ids) != len(set(user_ids)):
            raise OrbitMemberNotAllowedError(
                "Orbit members should contain only unique values."
            )

        if user_id in user_ids:
            raise OrbitMemberNotAllowedError("You can not add yourself to orbit.")

        org_members = await self.__user_repository.get_organization_members_by_user_ids(
            organization_id, user_ids
        )

        invalid_user_ids = set(user_ids) - {m.user.id for m in org_members}

        if invalid_user_ids:
            raise OrbitMemberNotAllowedError(
                f"Users {invalid_user_ids} are not in the organization."
            )

    async def create_organization_orbit(
        self, user_id: str, organization_id: str, orbit: OrbitCreateIn
    ) -> OrbitDetails:
        org_role = await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.CREATE,
        )

        await self._check_organization_orbits_limit(organization_id)
        secret = await self.__secret_repository.get_bucket_secret(
            orbit.bucket_secret_id
        )
        if not secret or secret.organization_id != organization_id:
            raise NotFoundError("Bucket secret not found")

        if orbit.members:
            await self._validate_orbit_members(user_id, organization_id, orbit.members)

        created_orbit = await self.__orbits_repository.create_orbit(
            organization_id, orbit
        )

        if not created_orbit:
            raise OrbitError("Some errors occurred when creating the orbit.")

        created_orbit.permissions = (
            self.__permissions_handler.get_orbit_permissions_by_role(org_role, None)
        )

        return created_orbit

    async def get_organization_orbits(
        self, user_id: str, organization_id: str
    ) -> list[Orbit]:
        org_role = await self.__permissions_handler.check_organization_permission(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.LIST,
        )
        if org_role in (OrgRole.OWNER, OrgRole.ADMIN):
            orbits = await self.__orbits_repository.get_organization_orbits(
                organization_id
            )
            return self._set_orbits_permissions(orbits, org_role)

        orbits = await self.__orbits_repository.get_organization_orbits_for_user(
            organization_id, user_id
        )
        return self._set_user_orbits_permissions(orbits)

    async def get_orbit(
        self, user_id: str, organization_id: str, orbit_id: str
    ) -> OrbitDetails:
        (
            org_role,
            orbit_role,
        ) = await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT,
            Action.READ,
        )

        orbit = await self.__orbits_repository.get_orbit(orbit_id, organization_id)

        if not orbit:
            raise OrbitNotFoundError()

        orbit.permissions = self.__permissions_handler.get_orbit_permissions_by_role(
            org_role, orbit_role
        )

        return orbit

    async def update_orbit(
        self,
        user_id: str,
        organization_id: str,
        orbit_id: str,
        orbit: OrbitUpdate,
    ) -> Orbit:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT,
            Action.UPDATE,
        )

        orbit_obj = await self.__orbits_repository.update_orbit(orbit_id, orbit)

        if not orbit_obj:
            raise OrbitNotFoundError()

        return orbit_obj

    async def delete_orbit(
        self, user_id: str, organization_id: str, orbit_id: str
    ) -> None:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT,
            Action.DELETE,
        )

        return await self.__orbits_repository.delete_orbit(orbit_id)

    async def get_orbit_members(
        self, user_id: str, organization_id: str, orbit_id: str
    ) -> list[OrbitMember]:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.LIST,
        )
        return await self.__orbits_repository.get_orbit_members(orbit_id)

    async def create_orbit_member(
        self, user_id: str, organization_id: str, member: OrbitMemberCreate
    ) -> OrbitMember:
        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            member.orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.CREATE,
        )

        org_member = await self.__user_repository.get_organization_member(
            organization_id, member.user_id
        )

        if not org_member:
            raise OrbitAccessDeniedError(
                "User must be a member of the organization to be added to an orbit."
            )

        if user_id == member.user_id:
            raise OrbitMemberNotAllowedError("You can not add yourself to orbit.")
        try:
            created_member = await self.__orbits_repository.create_orbit_member(member)
        except DatabaseConstraintError as error:
            raise OrbitMemberAlreadyExistsError() from error

        orbit = await self.__orbits_repository.get_orbit_simple(
            member.orbit_id, organization_id
        )

        self.__email_handler.send_added_to_orbit_email(
            created_member.user.full_name
            if created_member.user and created_member.user.full_name
            else "",
            created_member.user.email
            if created_member.user and created_member.user.email
            else "",
            orbit.name if orbit else "",
            config.APP_EMAIL_URL,
        )

        return created_member

    async def update_orbit_member(
        self,
        user_id: str,
        organization_id: str,
        orbit_id: str,
        member: UpdateOrbitMember,
    ) -> OrbitMember:
        member_obj = await self.__orbits_repository.get_orbit_member(member.id)

        if not member_obj:
            raise OrbitMemberNotFoundError()

        if user_id == member_obj.user.id:
            raise OrbitMemberNotAllowedError("You can not update your own data.")

        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.UPDATE,
        )
        updated = await self.__orbits_repository.update_orbit_member(member)

        if not updated:
            raise OrbitMemberNotFoundError()

        return updated

    async def delete_orbit_member(
        self,
        user_id: str,
        organization_id: str,
        orbit_id: str,
        member_id: str,
    ) -> None:
        member_obj = await self.__orbits_repository.get_orbit_member(member_id)

        if not member_obj:
            raise OrbitMemberNotFoundError()

        if user_id == member_obj.user.id:
            raise OrbitMemberNotAllowedError("You can not remove yourself from orbit.")

        await self.__permissions_handler.check_orbit_action_access(
            organization_id,
            orbit_id,
            user_id,
            Resource.ORBIT_USER,
            Action.DELETE,
        )
        return await self.__orbits_repository.delete_orbit_member(member_id)
