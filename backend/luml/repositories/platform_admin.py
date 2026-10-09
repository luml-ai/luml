from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from luml.models import (
    ArtifactOrm,
    OrbitOrm,
    OrganizationMemberOrm,
    OrganizationOrm,
    SatelliteOrm,
    UserOrm,
)
from luml.repositories.base import RepositoryBase
from luml.repositories.limits import OrganizationResource, organization_usage_query
from luml.schemas.organization import OrgRole
from luml.schemas.platform_admin import (
    OrganizationLimits,
    OrganizationLimitsUpdate,
    OrganizationUsage,
    PlatformAdminOrganization,
    PlatformAdminOrganizationDetails,
    PlatformAdminOrganizationMember,
    PlatformAdminOrganizationsPage,
    PlatformAdminUser,
    PlatformAdminUserDetails,
    PlatformAdminUserMembership,
    PlatformAdminUsersPage,
    PlatformAdminUserUpdate,
    PlatformStats,
)

_USAGE_COLUMNS = {
    resource: organization_usage_query(resource, OrganizationOrm.id)
    .scalar_subquery()
    .label(f"{resource.value}_usage")
    for resource in OrganizationResource
}

_ORGANIZATIONS_COUNT = (
    select(func.count(OrganizationMemberOrm.id))
    .where(OrganizationMemberOrm.user_id == UserOrm.id)
    .scalar_subquery()
    .label("organizations_count")
)


def _search_pattern(search: str) -> str:
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _to_admin_user(user: UserOrm, organizations_count: int) -> PlatformAdminUser:
    admin_user = PlatformAdminUser.model_validate(user)
    admin_user.organizations_count = organizations_count
    return admin_user


def _to_admin_organization(row: Any) -> PlatformAdminOrganization:  # noqa: ANN401
    organization: OrganizationOrm = row[0]
    return PlatformAdminOrganization(
        id=organization.id,
        name=organization.name,
        created_at=organization.created_at,
        limits=OrganizationLimits.model_validate(organization),
        usage=OrganizationUsage(
            members=row.members_usage,
            orbits=row.orbits_usage,
            satellites=row.satellites_usage,
            artifacts=row.artifacts_usage,
        ),
    )


class PlatformAdminRepository(RepositoryBase):
    async def get_stats(self) -> PlatformStats:
        created_since = datetime.now(UTC) - timedelta(days=30)
        async with self._get_session() as session:
            users = await self._count(session, select(func.count(UserOrm.id)))
            disabled_users = await self._count(
                session,
                select(func.count(UserOrm.id)).where(UserOrm.disabled.is_(True)),
            )
            recent_users = await self._count(
                session,
                select(func.count(UserOrm.id)).where(
                    UserOrm.created_at >= created_since
                ),
            )
            organizations = await self._count(
                session, select(func.count(OrganizationOrm.id))
            )
            orbits = await self._count(session, select(func.count(OrbitOrm.id)))
            satellites = await self._count(session, select(func.count(SatelliteOrm.id)))
            artifacts = await self._count(session, select(func.count(ArtifactOrm.id)))
        return PlatformStats(
            users=users,
            disabled_users=disabled_users,
            users_created_last_30_days=recent_users,
            organizations=organizations,
            orbits=orbits,
            satellites=satellites,
            artifacts=artifacts,
        )

    async def search_users(
        self, search: str | None, limit: int, offset: int
    ) -> PlatformAdminUsersPage:
        conditions = []
        if search:
            pattern = _search_pattern(search)
            conditions.append(
                or_(UserOrm.email.ilike(pattern), UserOrm.full_name.ilike(pattern))
            )
        async with self._get_session() as session:
            total = await self._count(
                session, select(func.count(UserOrm.id)).where(*conditions)
            )
            result = await session.execute(
                select(UserOrm, _ORGANIZATIONS_COUNT)
                .where(*conditions)
                .order_by(UserOrm.created_at.desc(), UserOrm.id.desc())
                .limit(limit)
                .offset(offset)
            )
            items = [_to_admin_user(user, count) for user, count in result.all()]
        return PlatformAdminUsersPage(items=items, total=total)

    async def get_user_details(self, user_id: UUID) -> PlatformAdminUserDetails | None:
        async with self._get_session() as session:
            user = await session.get(UserOrm, user_id)
            if user is None:
                return None
            result = await session.execute(
                select(OrganizationMemberOrm, OrganizationOrm.name)
                .join(
                    OrganizationOrm,
                    OrganizationMemberOrm.organization_id == OrganizationOrm.id,
                )
                .where(OrganizationMemberOrm.user_id == user_id)
                .order_by(OrganizationOrm.name)
            )
            memberships = [
                PlatformAdminUserMembership(
                    organization_id=member.organization_id,
                    organization_name=organization_name,
                    role=OrgRole(member.role),
                )
                for member, organization_name in result.all()
            ]
            base = _to_admin_user(user, len(memberships))
            return PlatformAdminUserDetails(
                **base.model_dump(),
                has_api_key=user.hashed_api_key is not None,
                memberships=memberships,
            )

    async def update_user(
        self, user_id: UUID, changes: PlatformAdminUserUpdate
    ) -> PlatformAdminUserDetails | None:
        async with self._get_session() as session:
            result = await session.execute(
                update(UserOrm)
                .where(UserOrm.id == user_id)
                .values(**changes.model_dump(exclude_none=True))
                .returning(UserOrm.id)
            )
            updated = result.scalar_one_or_none()
            await session.commit()
        if updated is None:
            return None
        return await self.get_user_details(user_id)

    async def search_organizations(
        self, search: str | None, limit: int, offset: int
    ) -> PlatformAdminOrganizationsPage:
        conditions = []
        if search:
            conditions.append(OrganizationOrm.name.ilike(_search_pattern(search)))
        async with self._get_session() as session:
            total = await self._count(
                session, select(func.count(OrganizationOrm.id)).where(*conditions)
            )
            result = await session.execute(
                self._organizations_query()
                .where(*conditions)
                .order_by(OrganizationOrm.created_at.desc(), OrganizationOrm.id.desc())
                .limit(limit)
                .offset(offset)
            )
            items = [_to_admin_organization(row) for row in result.all()]
        return PlatformAdminOrganizationsPage(items=items, total=total)

    async def get_organization_details(
        self, organization_id: UUID
    ) -> PlatformAdminOrganizationDetails | None:
        async with self._get_session() as session:
            result = await session.execute(
                self._organizations_query().where(OrganizationOrm.id == organization_id)
            )
            row = result.one_or_none()
            if row is None:
                return None
            members_result = await session.execute(
                select(OrganizationMemberOrm, UserOrm)
                .join(UserOrm, OrganizationMemberOrm.user_id == UserOrm.id)
                .where(OrganizationMemberOrm.organization_id == organization_id)
                .order_by(UserOrm.email)
            )
            members = [
                PlatformAdminOrganizationMember(
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=OrgRole(member.role),
                )
                for member, user in members_result.all()
            ]
        return PlatformAdminOrganizationDetails(
            **_to_admin_organization(row).model_dump(), members=members
        )

    async def update_organization_limits(
        self, organization_id: UUID, limits: OrganizationLimitsUpdate
    ) -> PlatformAdminOrganizationDetails | None:
        async with self._get_session() as session:
            result = await session.execute(
                update(OrganizationOrm)
                .where(OrganizationOrm.id == organization_id)
                .values(**limits.model_dump(exclude_none=True))
                .returning(OrganizationOrm.id)
            )
            updated = result.scalar_one_or_none()
            await session.commit()
        if updated is None:
            return None
        return await self.get_organization_details(organization_id)

    @staticmethod
    def _organizations_query() -> Select[Any]:
        return select(OrganizationOrm, *_USAGE_COLUMNS.values())

    @staticmethod
    async def _count(session: AsyncSession, query: Select[tuple[int]]) -> int:
        return await session.scalar(query) or 0
