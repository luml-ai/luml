from uuid import UUID

from luml.handlers.emails import EmailHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
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
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitMemberCreateSimple,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)
from luml.schemas.organization import OrgRole
from luml.schemas.permissions import Action, Resource
from luml.settings import config


class OrbitHandler:
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)
    __orbits_repository = OrbitRepository(engine)
    __permissions_handler = PermissionsHandler()
    __secret_repository = BucketSecretRepository(engine)

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

    async def _check_organization_orbits_limit(self, organization_id: UUID) -> None:
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
        user_id: UUID,
        organization_id: UUID,
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

    @staticmethod
    def get_members_notification_data(orbit: OrbitDetails) -> list[dict[str, str]]:
        if not orbit.members:
            return []

        return [
            {
                "name": member.user.full_name or "",
                "email": member.user.email or "",
                "orbit": orbit.name or "",
                "link": config.APP_EMAIL_URL,
            }
            for member in orbit.members
        ]

    async def create_organization_orbit(
        self, user_id: UUID, organization_id: UUID, orbit: OrbitCreateIn
    ) -> OrbitDetails:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.CREATE,
        )
        org_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        await self._check_organization_orbits_limit(organization_id)
        secret = await self.__secret_repository.get_bucket_secret(
            orbit.bucket_secret_id
        )
        if not secret or secret.organization_id != organization_id:
            raise NotFoundError("Bucket secret not found")

        if orbit.members:
            await self._validate_orbit_members(user_id, organization_id, orbit.members)

        if orbit.members is None:
            orbit.members = []

        orbit.members.append(
            OrbitMemberCreateSimple(user_id=user_id, role=OrbitRole.ADMIN)
        )

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
        self, user_id: UUID, organization_id: UUID
    ) -> list[Orbit]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.LIST,
        )
        org_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
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
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> OrbitDetails:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.READ,
            orbit_id,
        )
        org_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )
        orbit_role = await self.__orbits_repository.get_orbit_member_role(
            orbit_id, user_id
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
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        orbit: OrbitUpdate,
    ) -> Orbit:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.UPDATE,
            orbit_id,
        )

        orbit_obj = await self.__orbits_repository.update_orbit(orbit_id, orbit)

        if not orbit_obj:
            raise OrbitNotFoundError()

        return orbit_obj

    async def delete_orbit(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT,
            Action.DELETE,
            orbit_id,
        )

        return await self.__orbits_repository.delete_orbit(orbit_id)

    async def get_orbit_members(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> list[OrbitMember]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_USER,
            Action.LIST,
            orbit_id,
        )
        return await self.__orbits_repository.get_orbit_members(orbit_id)

    async def create_orbit_member(
        self, user_id: UUID, organization_id: UUID, member: OrbitMemberCreate
    ) -> OrbitMember:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_USER,
            Action.CREATE,
            member.orbit_id,
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
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        member: UpdateOrbitMember,
    ) -> OrbitMember:
        member_obj = await self.__orbits_repository.get_orbit_member(member.id)

        if not member_obj:
            raise OrbitMemberNotFoundError()

        if user_id == member_obj.user.id:
            raise OrbitMemberNotAllowedError("You can not update your own data.")

        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_USER,
            Action.UPDATE,
            orbit_id,
        )
        updated = await self.__orbits_repository.update_orbit_member(member)

        if not updated:
            raise OrbitMemberNotFoundError()

        return updated

    async def delete_orbit_member(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        member_id: UUID,
    ) -> None:
        member_obj = await self.__orbits_repository.get_orbit_member(member_id)

        if not member_obj:
            raise OrbitMemberNotFoundError()

        if user_id == member_obj.user.id:
            raise OrbitMemberNotAllowedError("You can not remove yourself from orbit.")

        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORBIT_USER,
            Action.DELETE,
            orbit_id,
        )
        return await self.__orbits_repository.delete_orbit_member(member_id)
