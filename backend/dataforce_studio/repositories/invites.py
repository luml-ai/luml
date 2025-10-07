from pydantic import EmailStr
from sqlalchemy.orm import joinedload

from dataforce_studio.models import OrganizationInviteOrm
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.base import ShortUUID
from dataforce_studio.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationInvite,
    OrganizationInviteSimple,
    UserInvite,
)


class InviteRepository(RepositoryBase, CrudMixin):
    async def create_organization_invite(
        self, invite: CreateOrganizationInvite
    ) -> OrganizationInviteSimple:
        async with self._get_session() as session:
            db_invite = await self.create_model(session, OrganizationInviteOrm, invite)
            return db_invite.to_organization_invite_simple()

    async def delete_organization_invite(self, invite_id: ShortUUID) -> None:
        async with self._get_session() as session, session.begin():
            return await self.delete_model(session, OrganizationInviteOrm, invite_id)

    async def get_organization_invite_by_email(
        self, organization_id: ShortUUID, email: EmailStr
    ) -> OrganizationInvite | None:
        async with self._get_session() as session:
            invite = await self.get_model_where(
                session,
                OrganizationInviteOrm,
                OrganizationInviteOrm.organization_id
                == ShortUUID(organization_id).to_uuid(),
                OrganizationInviteOrm.email == email,
                options=[
                    joinedload(OrganizationInviteOrm.invited_by_user),
                    joinedload(OrganizationInviteOrm.organization),
                ],
            )
            return invite.to_organization_invite() if invite else None

    async def get_invites_by_organization_id(
        self, organization_id: ShortUUID
    ) -> list[OrganizationInvite]:
        async with self._get_session() as session:
            invites = await self.get_models_where(
                session,
                OrganizationInviteOrm,
                OrganizationInviteOrm.organization_id
                == ShortUUID(organization_id).to_uuid(),
                options=[
                    joinedload(OrganizationInviteOrm.invited_by_user),
                    joinedload(OrganizationInviteOrm.organization),
                ],
            )
            return OrganizationInviteOrm.to_invites_list(invites)

    async def get_invites_by_user_email(self, email: EmailStr) -> list[UserInvite]:
        async with self._get_session() as session:
            invites = await self.get_models_where(
                session,
                OrganizationInviteOrm,
                OrganizationInviteOrm.email == email,
                options=[
                    joinedload(OrganizationInviteOrm.invited_by_user),
                    joinedload(OrganizationInviteOrm.organization),
                ],
            )
        return OrganizationInviteOrm.to_user_invites_list(invites)

    async def get_invite(self, invite_id: ShortUUID) -> OrganizationInvite | None:
        async with self._get_session() as session:
            db_invite = await self.get_model(
                session,
                OrganizationInviteOrm,
                invite_id,
                options=[
                    joinedload(OrganizationInviteOrm.invited_by_user),
                    joinedload(OrganizationInviteOrm.organization),
                ],
            )
            return db_invite.to_organization_invite() if db_invite else None

    async def delete_organization_invites_for_user(
        self, organization_id: ShortUUID, email: EmailStr
    ) -> None:
        async with self._get_session() as session, session.begin():
            return await self.delete_models_where(
                session,
                OrganizationInviteOrm,
                OrganizationInviteOrm.organization_id
                == ShortUUID(organization_id).to_uuid(),
                OrganizationInviteOrm.email == email,
            )

    async def delete_all_organization_invites(self, organization_id: ShortUUID) -> None:
        async with self._get_session() as session, session.begin():
            return await self.delete_models_where(
                session,
                OrganizationInviteOrm,
                OrganizationInviteOrm.organization_id
                == ShortUUID(organization_id).to_uuid(),
            )
