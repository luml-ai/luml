from uuid import UUID

from pydantic import EmailStr

from luml.handlers.emails import EmailHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    DatabaseConstraintError,
    EmailDeliveryError,
    InsufficientPermissionsError,
    NotFoundError,
    OrganizationDeleteError,
    OrganizationInviteAlreadyExistsError,
    OrganizationInviteNotFoundError,
    OrganizationLimitReachedError,
    OrganizationMemberAlreadyExistsError,
    OrganizationMemberNotFoundError,
)
from luml.repositories.invites import InviteRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import (
    CreateOrganizationInvite,
    CreateOrganizationInviteIn,
    Organization,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationInvite,
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationSwitcher,
    OrganizationUpdate,
    OrgRole,
    UpdateOrganizationMember,
    UserInvite,
)
from luml.schemas.permissions import Action, Resource
from luml.settings import config
from luml.utils.organizations import (
    get_invited_by_name,
    get_organization_email_name,
)


class OrganizationHandler:
    __invites_repository = InviteRepository(engine)
    __email_handler = EmailHandler()
    __user_repository = UserRepository(engine)
    __permissions_handler = PermissionsHandler()

    __organization_membership_limit = 5

    def _set_organizations_permissions(
        self, organizations: list[OrganizationSwitcher]
    ) -> list[OrganizationSwitcher]:
        for org in organizations:
            org.permissions = (
                self.__permissions_handler.get_organization_permissions_by_role(
                    org.role
                )
            )
        return organizations

    async def _organization_membership_limit_check(self, user_id: UUID) -> None:
        membership_num = (
            await self.__user_repository.get_user_organizations_membership_count(
                user_id
            )
        )

        if membership_num >= self.__organization_membership_limit:
            raise OrganizationLimitReachedError(
                "You’ve reached the limit of organizations you can join or create"
            )

    async def _check_org_members_limit(self, organization_id: UUID) -> None:
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")

        if organization.total_members >= organization.members_limit:
            raise OrganizationLimitReachedError(
                "Organization reached maximum number of users"
            )

    async def create_organization(
        self, user_id: UUID, organization: OrganizationCreateIn
    ) -> Organization:
        await self._organization_membership_limit_check(user_id)

        db_org = await self.__user_repository.create_organization(user_id, organization)
        return db_org.to_organization()

    async def update_organization(
        self,
        user_id: UUID,
        organization_id: UUID,
        organization: OrganizationUpdate,
    ) -> OrganizationDetails:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION, Action.UPDATE
        )

        if not await self.__user_repository.update_organization(
            organization_id, organization
        ):
            raise NotFoundError("Organization not found")

        organization_details = await self.__user_repository.get_organization_details(
            organization_id
        )

        if not organization_details:
            raise NotFoundError("Organization not found")

        return organization_details

    async def delete_organization(self, user_id: UUID, organization_id: UUID) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION, Action.DELETE
        )
        organization = await self.__user_repository.get_organization_details(
            organization_id
        )

        if not organization:
            raise NotFoundError("Organization not found")

        if len(organization.members) > 1:
            raise OrganizationDeleteError(
                "Organization has members and cant be deleted"
            )

        return await self.__user_repository.delete_organization(organization_id)

    async def leave_from_organization(
        self, user_id: UUID, organization_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION, Action.LEAVE
        )

        return await self.__user_repository.delete_organization_member_by_user_id(
            user_id, organization_id
        )

    async def get_user_organizations(self, user_id: UUID) -> list[OrganizationSwitcher]:
        organizations = await self.__user_repository.get_user_organizations(user_id)
        return self._set_organizations_permissions(organizations)

    async def get_organization(
        self, user_id: UUID, organization_id: UUID
    ) -> OrganizationDetails:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION, Action.READ
        )
        role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        organization = await self.__user_repository.get_organization_details(
            organization_id
        )
        if not organization:
            raise NotFoundError("Organization not found")

        organization.permissions = (
            self.__permissions_handler.get_organization_permissions_by_role(role)
        )
        return organization

    async def send_invite(
        self, user_id: UUID, invite_: CreateOrganizationInviteIn
    ) -> OrganizationInvite:
        await self.__permissions_handler.check_permissions(
            invite_.organization_id,
            user_id,
            Resource.ORGANIZATION_INVITE,
            Action.CREATE,
        )

        user_info = await self.__user_repository.get_public_user_by_id(user_id)

        if user_info and invite_.email == user_info.email:
            raise InsufficientPermissionsError("You can't invite yourself")

        member = await self.__user_repository.get_organization_member_by_email(
            invite_.organization_id, invite_.email
        )

        if member:
            raise OrganizationMemberAlreadyExistsError(
                "Already a member of the organization"
            )

        existing_invite = (
            await self.__invites_repository.get_organization_invite_by_email(
                invite_.organization_id, invite_.email
            )
        )

        if existing_invite:
            raise OrganizationInviteAlreadyExistsError()

        await self._check_org_members_limit(invite_.organization_id)

        db_created_invite = await self.__invites_repository.create_organization_invite(
            CreateOrganizationInvite(**invite_.model_dump(), invited_by=user_id)
        )
        invite = await self.__invites_repository.get_invite(db_created_invite.id)

        if not invite:
            raise OrganizationInviteNotFoundError()

        try:
            self.__email_handler.send_organization_invite_email(
                invite.email if invite else "",
                get_invited_by_name(invite),
                get_organization_email_name(invite),
                config.APP_EMAIL_URL,
            )
        except Exception as error:
            raise EmailDeliveryError(
                "Invite created successfully but email delivery failed.", 201
            ) from error

        return invite

    async def cancel_invite(
        self, user_id: UUID, organization_id: UUID, invite_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORGANIZATION_INVITE,
            Action.DELETE,
        )

        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def accept_invite(
        self, invite_id: UUID, user_id: UUID, user_email: EmailStr
    ) -> None:
        invite = await self.__invites_repository.get_invite(invite_id)

        if not invite:
            raise OrganizationInviteNotFoundError()

        if invite.email != user_email:
            raise InsufficientPermissionsError("This invite is not for you")

        await self._organization_membership_limit_check(user_id)
        await self._check_org_members_limit(invite.organization_id)

        try:
            await self.__user_repository.create_organization_member(
                OrganizationMemberCreate(
                    user_id=user_id,
                    organization_id=invite.organization_id,
                    role=invite.role,
                )
            )
        except DatabaseConstraintError as error:
            raise OrganizationMemberAlreadyExistsError() from error

        await self.__invites_repository.delete_organization_invites_for_user(
            invite.organization_id, invite.email
        )

    async def reject_invite(self, invite_id: UUID, user_email: EmailStr) -> None:
        invite = await self.__invites_repository.get_invite(invite_id)

        if not invite:
            raise OrganizationInviteNotFoundError()

        if invite.email != user_email:
            raise InsufficientPermissionsError("This invite is not for you")

        return await self.__invites_repository.delete_organization_invite(invite_id)

    async def get_organization_invites(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationInvite]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORGANIZATION_INVITE,
            Action.LIST,
        )

        return await self.__invites_repository.get_invites_by_organization_id(
            organization_id
        )

    async def get_user_invites(self, email: EmailStr) -> list[UserInvite]:
        return await self.__invites_repository.get_invites_by_user_email(email)

    async def get_organization_members_data(
        self, user_id: UUID, organization_id: UUID
    ) -> list[OrganizationMember]:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.ORGANIZATION_USER, Action.LIST
        )

        return await self.__user_repository.get_organization_members(organization_id)

    async def update_organization_member_by_id(
        self,
        user_id: UUID,
        organization_id: UUID,
        member_id: UUID,
        member: UpdateOrganizationMember,
    ) -> OrganizationMember | None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )
        user_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        member_to_update = await self.__user_repository.get_organization_member_by_id(
            member_id
        )

        if not member_to_update:
            raise OrganizationMemberNotFoundError()

        if user_id == member_to_update.user.id:
            raise InsufficientPermissionsError("You can not update your own data.")

        if user_role != OrgRole.OWNER and member.role == OrgRole.ADMIN:
            raise InsufficientPermissionsError(
                "Only Organization Owner can assign new admins."
            )

        return await self.__user_repository.update_organization_member(
            member_id, member
        )

    async def delete_organization_member_by_id(
        self, user_id: UUID, organization_id: UUID, member_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.DELETE,
        )

        member_to_delete = await self.__user_repository.get_organization_member_by_id(
            member_id
        )

        if not member_to_delete:
            raise OrganizationMemberNotFoundError()

        if user_id == member_to_delete.user.id:
            raise InsufficientPermissionsError(
                "You can not remove yourself from organization."
            )

        if member_to_delete and member_to_delete.role == OrgRole.OWNER:
            raise InsufficientPermissionsError("Organization Owner can not be removed.")

        return await self.__user_repository.delete_organization_member(member_id)

    async def add_organization_member(
        self,
        user_id: UUID,
        organization_id: UUID,
        member: OrganizationMemberCreate,
    ) -> OrganizationMember:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.ORGANIZATION_USER,
            Action.CREATE,
        )
        user_role = await self.__user_repository.get_organization_member_role(
            organization_id, user_id
        )

        await self._check_org_members_limit(organization_id)

        if user_role != OrgRole.OWNER and member.role == OrgRole.ADMIN:
            raise InsufficientPermissionsError(
                "Only Organization Owner can add new admins."
            )
        try:
            created_member = await self.__user_repository.create_organization_member(
                member
            )
        except DatabaseConstraintError as error:
            raise OrganizationMemberAlreadyExistsError() from error

        return created_member
