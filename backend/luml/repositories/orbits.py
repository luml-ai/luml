from typing import Any
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from luml.infra.exceptions import DatabaseConstraintError
from luml.models import OrbitMembersOrm, OrbitOrm
from luml.repositories.base import CrudMixin, RepositoryBase
from luml.schemas.orbit import (
    Orbit,
    OrbitCreate,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)
from luml.utils.organizations import convert_orbit_simple_members


class OrbitRepository(RepositoryBase, CrudMixin):
    async def get_organization_orbits(self, organization_id: UUID) -> list[Orbit]:
        async with self._get_session() as session:
            db_orbits = await self.get_models_where(
                session, OrbitOrm, OrbitOrm.organization_id == organization_id
            )
            return OrbitOrm.to_orbits_list(db_orbits)

    async def get_organization_orbits_for_user(
        self, organization_id: UUID, user_id: UUID
    ) -> list[Orbit]:
        async with self._get_session() as session:
            result = await session.execute(
                select(OrbitOrm, OrbitMembersOrm.role)
                .join(OrbitMembersOrm, OrbitMembersOrm.orbit_id == OrbitOrm.id)
                .where(
                    OrbitOrm.organization_id == organization_id,
                    OrbitMembersOrm.user_id == user_id,
                )
            )
            db_orbits = result.all()

            return [
                Orbit(
                    id=orbit.id,
                    name=orbit.name,
                    organization_id=orbit.organization_id,
                    bucket_secret_id=orbit.bucket_secret_id,
                    total_members=orbit.total_members,
                    total_collections=orbit.total_collections,
                    role=role,
                    created_at=orbit.created_at,
                    updated_at=orbit.updated_at,
                )
                for orbit, role in db_orbits
            ]

    async def get_orbit(
        self, orbit_id: UUID, organization_id: UUID
    ) -> OrbitDetails | None:
        async with self._get_session() as session:
            db_orbit = await self.get_model_where(
                session,
                OrbitOrm,
                OrbitOrm.id == orbit_id,
                OrbitOrm.organization_id == organization_id,
                options=[
                    selectinload(OrbitOrm.members).selectinload(OrbitMembersOrm.user)
                ],
            )

            if not db_orbit:
                return None

            db_orbit.members.sort(
                key=lambda m: {OrbitRole.ADMIN: 1, OrbitRole.MEMBER: 2}.get(
                    OrbitRole(m.role), 3
                )
            )

            return db_orbit.to_orbit_details()

    async def get_orbit_simple(
        self, orbit_id: UUID, organization_id: UUID
    ) -> Orbit | None:
        async with self._get_session() as session:
            db_orbit = await self.get_model_where(
                session,
                OrbitOrm,
                OrbitOrm.id == orbit_id,
                OrbitOrm.organization_id == organization_id,
            )

            return db_orbit.to_orbit() if db_orbit else None

    async def get_orbit_by_id(self, orbit_id: UUID) -> Orbit | None:
        async with self._get_session() as session:
            db_orbit = await self.get_model(session, OrbitOrm, orbit_id)
            return db_orbit.to_orbit() if db_orbit else None

    async def create_orbit(
        self, organization_id: UUID, orbit: OrbitCreateIn
    ) -> OrbitDetails | None:
        async with self._get_session() as session:
            db_orbit = await self.create_model(
                session,
                OrbitOrm,
                OrbitCreate(
                    name=orbit.name,
                    bucket_secret_id=orbit.bucket_secret_id,
                    organization_id=organization_id,
                ),
            )
            if orbit.members:
                await self.create_models(
                    session,
                    OrbitMembersOrm,
                    convert_orbit_simple_members(db_orbit.id, orbit.members),
                )

            return await self.get_orbit(db_orbit.id, organization_id)

    async def update_orbit(self, orbit_id: UUID, orbit: OrbitUpdate) -> Orbit | None:
        orbit.id = orbit_id

        async with self._get_session() as session:
            db_orbit = await self.update_model(session, OrbitOrm, orbit)
            return db_orbit.to_orbit() if db_orbit else None

    async def delete_orbit(self, orbit_id: UUID) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrbitOrm, orbit_id)

    async def get_orbit_members(self, orbit_id: UUID) -> list[OrbitMember]:
        async with self._get_session() as session:
            db_members = await self.get_models_where(
                session,
                OrbitMembersOrm,
                OrbitMembersOrm.orbit_id == orbit_id,
                order_by=[
                    case(
                        (OrbitMembersOrm.role == OrbitRole.ADMIN, 1),
                        (OrbitMembersOrm.role == OrbitRole.MEMBER, 2),
                        else_=3,
                    ),
                ],
            )
            return OrbitMembersOrm.to_orbit_members_list(db_members)

    async def get_orbit_member(self, member_id: UUID) -> OrbitMember | None:
        async with self._get_session() as session:
            db_member = await self.get_model(session, OrbitMembersOrm, member_id)
            return db_member.to_orbit_member() if db_member else None

    async def get_orbit_member_where(
        self,
        *where_conditions: Any,  # noqa: ANN401
    ) -> OrbitMembersOrm | None:
        async with self._get_session() as session:
            return await self.get_model_where(
                session, OrbitMembersOrm, *where_conditions
            )

    async def create_orbit_member(self, member: OrbitMemberCreate) -> OrbitMember:
        async with self._get_session() as session:
            try:
                db_member = await self.create_model(session, OrbitMembersOrm, member)
            except IntegrityError as error:
                raise DatabaseConstraintError() from error
            return db_member.to_orbit_member()

    async def create_orbit_members(
        self, members: list[OrbitMemberCreate]
    ) -> list[OrbitMember]:
        async with self._get_session() as session:
            db_members = await self.create_models(session, OrbitMembersOrm, members)
            return [member.to_orbit_member() for member in db_members]

    async def update_orbit_member(
        self, member: UpdateOrbitMember
    ) -> OrbitMember | None:
        async with self._get_session() as session:
            db_member = await self.update_model(
                session=session, orm_class=OrbitMembersOrm, data=member
            )
            return db_member.to_orbit_member() if db_member else None

    async def delete_orbit_member(self, member_id: UUID) -> None:
        async with self._get_session() as session:
            return await self.delete_model(session, OrbitMembersOrm, member_id)

    async def get_organization_orbits_count(self, organization_id: UUID) -> int:
        async with self._get_session() as session:
            return await self.get_model_count(
                session, OrbitOrm, OrbitOrm.organization_id == organization_id
            )

    async def get_orbit_members_count(self, orbit_id: UUID) -> int:
        async with self._get_session() as session:
            return await self.get_model_count(
                session, OrbitMembersOrm, OrbitMembersOrm.orbit_id == orbit_id
            )

    async def get_orbit_member_role(self, orbit_id: UUID, user_id: UUID) -> str | None:
        member = await self.get_orbit_member_where(
            OrbitMembersOrm.orbit_id == orbit_id, OrbitMembersOrm.user_id == user_id
        )
        return str(member.role) if member else None
