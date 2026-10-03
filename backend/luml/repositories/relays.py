from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from luml.infra.exceptions import DatabaseConstraintError, RelayHasUnendedSessionsError
from luml.models import LiveSessionOrm, RelayOrm
from luml.models.live_session import live_session_unended
from luml.repositories.base import RepositoryBase
from luml.schemas.relay import Relay, RelayCreate, RelayUpdateIn


def _usable_by(organization_id: UUID) -> ColumnElement[bool]:
    return or_(
        RelayOrm.organization_id == organization_id,
        RelayOrm.organization_id.is_(None),
    )


async def _count_unended_sessions(session: AsyncSession, relay_id: UUID) -> int:
    unended = await session.scalar(
        select(func.count(LiveSessionOrm.id)).where(
            LiveSessionOrm.relay_id == relay_id,
            live_session_unended(datetime.now(UTC)),
        )
    )
    return unended or 0


class RelayRepository(RepositoryBase):
    async def list_usable_relays(self, organization_id: UUID) -> list[Relay]:
        async with self._get_session() as session:
            result = await session.execute(
                select(RelayOrm)
                .where(_usable_by(organization_id))
                .order_by(RelayOrm.label, RelayOrm.id)
            )
            return [relay.to_relay() for relay in result.scalars().all()]

    async def get_relay(
        self, relay_id: UUID, organization_id: UUID | None = None
    ) -> Relay | None:
        """Read a relay; with an organization, only one it owns or a managed one."""
        async with self._get_session() as session:
            query = select(RelayOrm).where(RelayOrm.id == relay_id)
            if organization_id is not None:
                query = query.where(_usable_by(organization_id))
            relay = (await session.execute(query)).scalar_one_or_none()
            return relay.to_relay() if relay else None

    async def create_relay(self, data: RelayCreate) -> Relay:
        async with self._get_session() as session:
            relay = RelayOrm(**data.model_dump())
            session.add(relay)
            try:
                await session.commit()
            except IntegrityError as error:
                raise DatabaseConstraintError() from error
            await session.refresh(relay)
            return relay.to_relay()

    async def update_relay(self, relay_id: UUID, data: RelayUpdateIn) -> Relay | None:
        """Update a relay, refusing an address change while it has unended sessions.

        Running sessions derive their public addresses from the base domain
        and the agent address, so those wait until every session has ended.
        """
        changes = data.model_dump(exclude_unset=True)
        async with self._get_session() as session:
            # The row lock makes a concurrent session start on this relay wait
            # for its foreign key check, so the count below cannot go stale.
            relay = await session.get(RelayOrm, relay_id, with_for_update=True)
            if relay is None:
                return None
            moves = any(
                field in changes and changes[field] != getattr(relay, field)
                for field in ("base_domain", "agent_url")
            )
            if moves and (unended := await _count_unended_sessions(session, relay_id)):
                raise RelayHasUnendedSessionsError(
                    "change the base domain or agent address", unended
                )
            for field, value in changes.items():
                setattr(relay, field, value)
            try:
                await session.commit()
            except IntegrityError as error:
                raise DatabaseConstraintError() from error
            await session.refresh(relay)
            return relay.to_relay()

    async def rotate_token(
        self, relay_id: UUID, token_hash: str, previous_token_expires_at: datetime
    ) -> Relay | None:
        # One statement, so the current hash moves to the previous slot even
        # when two rotations race; a hash already there is retired at once.
        async with self._get_session() as session:
            result = await session.execute(
                update(RelayOrm)
                .where(RelayOrm.id == relay_id)
                .values(
                    previous_token_hash=RelayOrm.token_hash,
                    previous_token_expires_at=previous_token_expires_at,
                    token_hash=token_hash,
                )
                .returning(RelayOrm)
            )
            relay = result.scalar_one_or_none()
            rotated = relay.to_relay() if relay else None
            await session.commit()
            return rotated

    async def record_report(self, relay_id: UUID, connected_agents: int) -> None:
        async with self._get_session() as session:
            await session.execute(
                update(RelayOrm)
                .where(RelayOrm.id == relay_id)
                .values(
                    last_seen_at=datetime.now(UTC), connected_agents=connected_agents
                )
            )
            await session.commit()

    async def get_relay_by_token_hash(self, token_hash: str) -> Relay | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(RelayOrm).where(
                    or_(
                        RelayOrm.token_hash == token_hash,
                        and_(
                            RelayOrm.previous_token_hash == token_hash,
                            RelayOrm.previous_token_expires_at > datetime.now(UTC),
                        ),
                    )
                )
            )
            relay = result.scalar_one_or_none()
            return relay.to_relay() if relay else None

    async def delete_relay(self, relay_id: UUID) -> bool:
        """Remove a relay once every session on it has ended.

        Its orbits lose the assignment and its ended sessions lose the
        reference, both through their foreign keys.
        """
        async with self._get_session() as session:
            relay = await session.get(RelayOrm, relay_id, with_for_update=True)
            if relay is None:
                return False
            if unended := await _count_unended_sessions(session, relay_id):
                raise RelayHasUnendedSessionsError("remove the relay", unended)
            await session.delete(relay)
            await session.commit()
            return True
