import secrets
import string
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from luml.models import LiveSessionOrm
from luml.models.live_session import live_session_unended
from luml.repositories.base import RepositoryBase, violates
from luml.repositories.limits import OrganizationResource, reserve_organization_slot
from luml.schemas.live_session import (
    LIVE_SESSION_ENDED_AFTER,
    LIVE_SESSION_LIST_RETENTION,
    LiveSession,
    LiveSessionCreate,
)

SESSION_ID_ALPHABET = string.ascii_lowercase + string.digits
SESSION_ID_LENGTH = 12
_MAX_ID_ATTEMPTS = 5


def new_session_id() -> str:
    return "".join(
        secrets.choice(SESSION_ID_ALPHABET) for _ in range(SESSION_ID_LENGTH)
    )


_last_sign_of_life = func.coalesce(
    LiveSessionOrm.last_heartbeat_at, LiveSessionOrm.started_at
)


class LiveSessionRepository(RepositoryBase):
    async def check_session_slot(
        self, organization_id: UUID, limit: OrganizationResource
    ) -> None:
        async with self._get_session() as session:
            await reserve_organization_slot(session, organization_id, limit, lock=False)

    async def create_live_session(
        self,
        data: LiveSessionCreate,
        organization_id: UUID,
        limit: OrganizationResource,
    ) -> LiveSession:
        # The primary key refuses an identifier that was handed out before;
        # a clash is retried with a new one.
        for _ in range(_MAX_ID_ATTEMPTS - 1):
            try:
                return await self._insert_live_session(data, organization_id, limit)
            except IntegrityError as error:
                if not violates(error, "live_sessions_pkey"):
                    raise
        return await self._insert_live_session(data, organization_id, limit)

    async def _insert_live_session(
        self,
        data: LiveSessionCreate,
        organization_id: UUID,
        limit: OrganizationResource,
    ) -> LiveSession:
        async with self._get_session() as session:
            await reserve_organization_slot(session, organization_id, limit)
            db_session = LiveSessionOrm(
                id=new_session_id(), started_at=datetime.now(UTC), **data.model_dump()
            )
            session.add(db_session)
            await session.commit()
            await session.refresh(db_session)
            return db_session.to_live_session()

    async def get_live_session(self, session_id: str) -> LiveSession | None:
        async with self._get_session() as session:
            db_session = await session.get(LiveSessionOrm, session_id)
            return db_session.to_live_session() if db_session else None

    async def list_live_sessions(
        self, orbit_id: UUID, user_id: UUID
    ) -> list[LiveSession]:
        now = datetime.now(UTC)
        ended_at = func.coalesce(
            LiveSessionOrm.ended_at, _last_sign_of_life + LIVE_SESSION_ENDED_AFTER
        )
        async with self._get_session() as session:
            result = await session.execute(
                select(LiveSessionOrm)
                .where(
                    LiveSessionOrm.orbit_id == orbit_id,
                    LiveSessionOrm.user_id == user_id,
                    ended_at > now - LIVE_SESSION_LIST_RETENTION,
                )
                .order_by(LiveSessionOrm.started_at.desc())
            )
            return [row.to_live_session() for row in result.scalars().all()]

    async def record_heartbeat(
        self, session_id: str, connected: bool
    ) -> LiveSession | None:
        """Record a heartbeat unless the session has already ended.

        An ended session is returned unchanged, so the caller sees its status.
        """
        now = datetime.now(UTC)
        async with self._get_session() as session:
            recorded = await session.scalar(
                update(LiveSessionOrm)
                .where(LiveSessionOrm.id == session_id, live_session_unended(now))
                .values(last_heartbeat_at=now, connected=connected)
                .returning(LiveSessionOrm)
            )
            live_session = recorded.to_live_session() if recorded else None
            await session.commit()
        return live_session or await self.get_live_session(session_id)

    async def end_live_session(self, session_id: str) -> LiveSession | None:
        # A session that went silent ended when its silence reached the limit,
        # which keeps its place in the list from being extended by a late end.
        ended_at = func.least(
            datetime.now(UTC), _last_sign_of_life + LIVE_SESSION_ENDED_AFTER
        )
        async with self._get_session() as session:
            await session.execute(
                update(LiveSessionOrm)
                .where(
                    LiveSessionOrm.id == session_id,
                    LiveSessionOrm.ended_at.is_(None),
                )
                .values(ended_at=ended_at)
            )
            await session.commit()
        return await self.get_live_session(session_id)
