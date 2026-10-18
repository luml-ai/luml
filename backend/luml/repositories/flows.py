from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, delete, not_, select
from sqlalchemy.exc import IntegrityError

from luml.models import FlowOrm, LiveSessionOrm
from luml.models.flow import FLOW_NAME_CONSTRAINT
from luml.models.live_session import live_session_unended, live_session_visible_to
from luml.repositories.base import RepositoryBase, violates
from luml.schemas.flow import Flow, FlowCreate

_MAX_ATTACH_ATTEMPTS = 2


def _visible_flows(orbit_id: UUID, user_id: UUID) -> Select[tuple[FlowOrm]]:
    """Flows of the orbit whose session the user may see and has not ended."""
    return (
        select(FlowOrm)
        .join(LiveSessionOrm, FlowOrm.session_id == LiveSessionOrm.id)
        .where(
            FlowOrm.orbit_id == orbit_id,
            live_session_visible_to(user_id),
            live_session_unended(datetime.now(UTC)),
        )
    )


class FlowRepository(RepositoryBase):
    async def delete_gone_flows(self) -> None:
        """Delete flows whose session has ended, freeing their names.

        Runs on every flow write instead of on a schedule.
        """
        ended_sessions = select(LiveSessionOrm.id).where(
            not_(live_session_unended(datetime.now(UTC)))
        )
        async with self._get_session() as session:
            await session.execute(
                delete(FlowOrm).where(FlowOrm.session_id.in_(ended_sessions))
            )
            await session.commit()

    async def get_flow_by_name(
        self, orbit_id: UUID, user_id: UUID, name: str
    ) -> Flow | None:
        async with self._get_session() as session:
            db_flow = await session.scalar(
                select(FlowOrm).where(
                    FlowOrm.orbit_id == orbit_id,
                    FlowOrm.user_id == user_id,
                    FlowOrm.name == name,
                )
            )
            return db_flow.to_flow() if db_flow else None

    async def attach_session(self, data: FlowCreate) -> tuple[Flow, str | None]:
        """Create the flow with its session, or point the existing one at it.

        Returns the flow and the session it pointed at before, if any. An
        insert that loses the name to a concurrent one points that flow instead.
        """
        for _ in range(_MAX_ATTACH_ATTEMPTS - 1):
            try:
                return await self._attach_session(data)
            except IntegrityError as error:
                if not violates(error, FLOW_NAME_CONSTRAINT):
                    raise
        return await self._attach_session(data)

    async def _attach_session(self, data: FlowCreate) -> tuple[Flow, str | None]:
        async with self._get_session() as session:
            db_flow = await session.scalar(
                select(FlowOrm)
                .where(
                    FlowOrm.orbit_id == data.orbit_id,
                    FlowOrm.user_id == data.user_id,
                    FlowOrm.name == data.name,
                )
                .with_for_update(of=FlowOrm)
            )
            previous_session_id = db_flow.session_id if db_flow else None
            if db_flow is None:
                db_flow = FlowOrm(**data.model_dump())
                session.add(db_flow)
            else:
                db_flow.session_id = data.session_id
            await session.commit()
            await session.refresh(db_flow)
            return db_flow.to_flow(), previous_session_id

    async def list_flows(self, orbit_id: UUID, user_id: UUID) -> list[Flow]:
        async with self._get_session() as session:
            result = await session.scalars(
                _visible_flows(orbit_id, user_id).order_by(FlowOrm.created_at.desc())
            )
            return [db_flow.to_flow() for db_flow in result.all()]

    async def get_flow(
        self, orbit_id: UUID, flow_id: UUID, user_id: UUID
    ) -> Flow | None:
        async with self._get_session() as session:
            db_flow = await session.scalar(
                _visible_flows(orbit_id, user_id).where(FlowOrm.id == flow_id)
            )
            return db_flow.to_flow() if db_flow else None

    async def delete_flow(self, flow_id: UUID, session_id: str) -> None:
        """Delete the flow only while it still points at `session_id`; a flow
        exposed again meanwhile points at its new session and stays."""
        async with self._get_session() as session:
            await session.execute(
                delete(FlowOrm).where(
                    FlowOrm.id == flow_id, FlowOrm.session_id == session_id
                )
            )
            await session.commit()
