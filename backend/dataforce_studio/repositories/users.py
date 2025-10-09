from typing import Any
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from dataforce_studio.infra.exceptions import DatabaseConstraintError
from dataforce_studio.models import (
    OrganizationInviteOrm,
    OrganizationMemberOrm,
    OrganizationOrm,
    StatsEmailSendOrm,
    UserOrm,
)
from dataforce_studio.repositories.base import CrudMixin, RepositoryBase
from dataforce_studio.schemas.organization import (
    Organization,
    OrganizationCreate,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationMember,
    OrganizationMemberCreate,
    OrganizationOwnerCreate,
    OrganizationSwitcher,
    OrganizationUpdate,
    OrgRole,
    UpdateOrganizationMember,
)
from dataforce_studio.schemas.stats import StatsEmailSendCreate, StatsEmailSendOut
from dataforce_studio.schemas.user import (
    CreateUser,
    UpdateUser,
    UpdateUserAPIKey,
    User,
    UserOut,
)
from dataforce_studio.utils.organizations import (
    generate_organization_name,
    get_members_roles_count,
)


class UserRepository(RepositoryBase, CrudMixin):
    async def create_user(
        self,
        create_user: CreateUser,
    ) -> User:
        async with self._get_session() as session:
            db_user = UserOrm.from_user(create_user)
            session.add(db_user)

            await session.flush()
            await session.refresh(db_user)
            user_response = db_user.to_user()

            db_organization = OrganizationOrm(
                name=generate_organization_name(
                    create_user.email, create_user.full_name
                )
            )
            session.add(db_organization)
            await session.flush()

            db_organization_member = OrganizationMemberOrm(
                user_id=db_user.id,
                organization_id=db_organization.id,
                role=OrgRole.OWNER,
            )
            session.add(db_organization_member)

            await session.commit()
        return user_response

    async def get_user(self, email: EmailStr) -> User | None:
        async with self._get_session() as session:
            db_user = await self.get_model_where(
                session, UserOrm, UserOrm.email == email
            )
            return db_user.to_user() if db_user else None

    async def get_public_user(self, email: EmailStr) -> UserOut | None:
        async with self._get_session() as session:
            db_user = await self.get_model_where(
                session, UserOrm, UserOrm.email == email
            )
            return db_user.to_public_user() if db_user else None

    async def get_public_user_by_id(self, user_id: UUID) -> UserOut | None:
        async with self._get_session() as session:
            db_user = await self.get_model(session, UserOrm, user_id)
            return db_user.to_public_user() if db_user else None

    async def delete_user(self, email: EmailStr) -> None:
        async with self._get_session() as session:
            return await self.delete_model_where(
                session, UserOrm, UserOrm.email == email
            )

    async def update_user(
        self,
        update_user: UpdateUser,
    ) -> bool:
        async with self._get_session() as session:
            changed = False
            result = await session.execute(
                select(UserOrm).filter(UserOrm.email == update_user.email)
            )

            if not (db_user := result.scalars().first()):
                return False

            fields_to_update = update_user.model_dump(exclude_unset=True)

            for field, value in fields_to_update.items():
                setattr(db_user, field, value)
                changed = True

            if changed:
                await session.commit()
        return changed

    async def create_organization(
        self, user_id: UUID, organization: OrganizationCreateIn
    ) -> OrganizationOrm:
        async with self._get_session() as session:
            org_logo = str(organization.logo) if organization.logo else None
            db_organization = await self.create_model(
                session,
                OrganizationOrm,
                OrganizationCreate(name=organization.name, logo=org_logo),
            )
            await self.create_owner(user_id, db_organization.id)

            return db_organization

    async def update_organization(
        self,
        organization_id: UUID,
        organization: OrganizationUpdate,
    ) -> Organization | None:
        organization.id = organization_id
        organization.logo = str(organization.logo) if organization.logo else None

        async with self._get_session() as session:
            db_organization = await self.update_model(
                session=session, orm_class=OrganizationOrm, data=organization
            )
            return db_organization.to_organization() if db_organization else None

    async def delete_organization(self, organization_id: UUID) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrganizationOrm, organization_id)

    async def get_organization_members_count(self, organization_id: UUID) -> int:
        async with self._get_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(OrganizationMemberOrm)
                .where(OrganizationMemberOrm.organization_id == organization_id)
            )
        return result.scalar() or 0

    async def create_organization_member(
        self, member: OrganizationMemberCreate
    ) -> OrganizationMember:
        async with self._get_session() as session:
            try:
                db_member = await self.create_model(
                    session, OrganizationMemberOrm, member
                )
            except IntegrityError as error:
                raise DatabaseConstraintError() from error
            return db_member.to_organization_member()

    async def create_owner(
        self, user_id: UUID, organization_id: UUID
    ) -> OrganizationMember:
        async with self._get_session() as session:
            db_member = await self.create_model(
                session,
                OrganizationMemberOrm,
                OrganizationOwnerCreate(
                    user_id=user_id, organization_id=organization_id, role=OrgRole.OWNER
                ),
            )
            return db_member.to_organization_member()

    async def get_user_organizations(self, user_id: UUID) -> list[OrganizationSwitcher]:
        async with self._get_session() as session:
            db_organizations = await self.get_models_where(
                session,
                OrganizationOrm,
                OrganizationMemberOrm.user_id == user_id,
                order_by=[OrganizationOrm.name],
                join_condition=(
                    OrganizationMemberOrm,
                    OrganizationMemberOrm.organization_id == OrganizationOrm.id,
                ),
                select_fields=[OrganizationOrm, OrganizationMemberOrm.role],
                use_unique=True,
            )

            return [
                OrganizationSwitcher(
                    id=org.id,
                    name=org.name,
                    logo=org.logo,
                    role=member_role,
                    created_at=org.created_at,
                    updated_at=org.updated_at,
                )
                for org, member_role in db_organizations
            ]

    async def get_organization_details(
        self, organization_id: UUID
    ) -> OrganizationDetails | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationOrm)
                .options(
                    joinedload(OrganizationOrm.members).joinedload(
                        OrganizationMemberOrm.user
                    ),
                    joinedload(OrganizationOrm.invites).joinedload(
                        OrganizationInviteOrm.organization
                    ),
                    joinedload(OrganizationOrm.orbits),
                )
                .where(OrganizationOrm.id == organization_id)
            )
            db_organization = result.unique().scalar_one_or_none()

            if not db_organization:
                return None

            details = OrganizationDetails.model_validate(db_organization)
            details.total_orbits = len(db_organization.orbits)
            details.total_members = len(db_organization.members)
            details.members_by_role = get_members_roles_count(db_organization.members)

            return details

    async def get_organization_users(
        self, organization_id: UUID
    ) -> list[OrganizationMember]:
        async with self._get_session() as session:
            db_members = await self.get_models_where(
                session,
                OrganizationMemberOrm,
                OrganizationMemberOrm.organization_id == organization_id,
            )
            return OrganizationMemberOrm.to_organization_members(db_members)

    async def update_organization_member(
        self, member_id: UUID, member: UpdateOrganizationMember
    ) -> OrganizationMember | None:
        member.id = member_id
        async with self._get_session() as session:
            db_member = await self.update_model(session, OrganizationMemberOrm, member)
            return db_member.to_organization_member() if db_member else None

    async def delete_organization_member(self, member_id: UUID) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrganizationMemberOrm, member_id)

    async def delete_organization_member_where(self, *where_conditions: Any) -> None:  # noqa: ANN401
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm).where(*where_conditions)
            )
            member = result.scalar_one_or_none()

            if member:
                await session.delete(member)
                await session.commit()

    async def delete_organization_member_by_user_id(
        self, user_id: UUID, organization_id: UUID
    ) -> None:
        return await self.delete_organization_member_where(
            OrganizationMemberOrm.user_id == user_id,
            OrganizationMemberOrm.organization_id == organization_id,
        )

    async def get_organization_members(
        self, organization_id: UUID
    ) -> list[OrganizationMember]:
        async with self._get_session() as session, session.begin():
            db_members = await self.get_models_where(
                session,
                OrganizationMemberOrm,
                (OrganizationMemberOrm.organization_id == organization_id),
                options=[joinedload(OrganizationMemberOrm.user)],
                order_by=[
                    case(
                        (OrganizationMemberOrm.role == "OWNER", 0),
                        (OrganizationMemberOrm.role == "ADMIN", 1),
                        (OrganizationMemberOrm.role == "MEMBER", 2),
                        else_=3,
                    ),
                    OrganizationMemberOrm.created_at,
                ],
            )

            return OrganizationMemberOrm.to_organization_members(db_members)

    async def get_organization_member(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMemberOrm | None:
        async with self._get_session() as session:
            return await self.get_model_where(
                session,
                OrganizationMemberOrm,
                OrganizationMemberOrm.user_id == user_id,
                OrganizationMemberOrm.organization_id == organization_id,
            )

    async def get_organization_member_by_id(
        self, member_id: UUID
    ) -> OrganizationMember | None:
        async with self._get_session() as session:
            db_member = await self.get_model(session, OrganizationMemberOrm, member_id)
            return db_member.to_organization_member() if db_member else None

    async def get_organization_member_by_email(
        self, organization_id: UUID, email: EmailStr
    ) -> OrganizationMember | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrganizationMemberOrm)
                .join(OrganizationMemberOrm.user)
                .where(
                    OrganizationMemberOrm.organization_id == organization_id,
                    UserOrm.email == email,
                )
                .options(selectinload(OrganizationMemberOrm.user))
            )
            db_member = result.scalar_one_or_none()
            return db_member.to_organization_member() if db_member else None

    async def get_organization_member_role(
        self, organization_id: UUID, user_id: UUID
    ) -> str | None:
        member = await self.get_organization_member(organization_id, user_id)
        return str(member.role) if member else None

    async def get_organization_members_by_user_ids(
        self, organization_id: UUID, user_ids: list[UUID]
    ) -> list[OrganizationMember]:
        async with self._get_session() as session:
            db_members = await self.get_models_where(
                session,
                OrganizationMemberOrm,
                OrganizationMemberOrm.organization_id == organization_id,
                OrganizationMemberOrm.user_id.in_(user_ids),
            )
            return [member.to_organization_member() for member in db_members]

    async def get_user_organizations_membership_count(self, user_id: UUID) -> int:
        async with self._get_session() as session:
            return await self.get_model_count(
                session, OrganizationMemberOrm, OrganizationMemberOrm.user_id == user_id
            )

    async def create_stats_email_send_obj(
        self, stat: StatsEmailSendCreate
    ) -> StatsEmailSendOut:
        async with self._get_session() as session:
            db_email_send = await self.create_model(session, StatsEmailSendOrm, stat)
            return db_email_send.to_email_send()

    async def create_user_api_key(self, user: UpdateUserAPIKey) -> bool:
        async with self._get_session() as session:
            db_user = await self.update_model(session, UserOrm, user)
            return bool(db_user and db_user.hashed_api_key)

    async def get_user_by_api_key_hash(self, key_hash: str) -> UserOut | None:
        async with self._get_session() as session:
            db_user = await self.get_model_where(
                session, UserOrm, UserOrm.hashed_api_key == key_hash
            )
            return db_user.to_public_user() if db_user else None

    async def delete_api_key_by_user_id(self, user_id: UUID) -> None:
        async with self._get_session() as session:
            await self.update_model(
                session, UserOrm, UpdateUserAPIKey(id=user_id, hashed_api_key=None)
            )
