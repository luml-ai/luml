from uuid import UUID

from luml.handlers.live_sessions import LiveSessionHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import NotFoundError
from luml.repositories.flows import FlowRepository
from luml.schemas.flow import Flow, FlowCreate, FlowExposeIn, FlowExposeOut
from luml.schemas.live_session import LiveSessionStartIn
from luml.schemas.permissions import Action, Resource
from luml.settings import Settings, config


class FlowHandler:
    __repo = FlowRepository(engine)
    __permissions_handler = PermissionsHandler()

    def __init__(self, settings: Settings = config) -> None:
        self._live_sessions = LiveSessionHandler(settings)
        self._app_url = settings.APP_EMAIL_URL.rstrip("/")

    async def _authorize(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, action: Action
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id, user_id, Resource.LIVE_SESSION, action, orbit_id
        )

    async def _get_visible_flow(
        self, user_id: UUID, orbit_id: UUID, flow_id: UUID
    ) -> Flow:
        flow = await self.__repo.get_flow(orbit_id, flow_id, user_id)
        if flow is None:
            raise NotFoundError("Flow not found")
        return flow

    async def expose_flow(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        data: FlowExposeIn,
    ) -> FlowExposeOut:
        await self._authorize(user_id, organization_id, orbit_id, Action.CREATE)
        await self.__repo.delete_gone_flows()
        found = await self.__repo.get_flow_by_name(orbit_id, user_id, data.name)
        replacing = found.session.id if found else None
        # Every start refusal is raised here, before the found flow's session
        # is ended or anything is created.
        started = await self._live_sessions.start_session(
            user_id,
            organization_id,
            orbit_id,
            LiveSessionStartIn(label=data.name),
            replacing=replacing,
        )
        flow, previous_session_id = await self.__repo.attach_session(
            FlowCreate(
                orbit_id=orbit_id,
                user_id=user_id,
                name=data.name,
                session_id=started.id,
            )
        )
        if previous_session_id is not None and previous_session_id != replacing:
            # A concurrent expose of the name pointed the flow at its own session.
            await self._live_sessions.end_session(
                user_id, organization_id, orbit_id, previous_session_id
            )
        return FlowExposeOut(
            flow=flow,
            session=started,
            app_url=(
                f"{self._app_url}/organization/{organization_id}/orbit/{orbit_id}/flow"
            ),
        )

    async def list_flows(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> list[Flow]:
        await self._authorize(user_id, organization_id, orbit_id, Action.LIST)
        return await self.__repo.list_flows(orbit_id, user_id)

    async def get_flow(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, flow_id: UUID
    ) -> Flow:
        await self._authorize(user_id, organization_id, orbit_id, Action.READ)
        return await self._get_visible_flow(user_id, orbit_id, flow_id)

    async def remove_flow(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, flow_id: UUID
    ) -> None:
        await self._authorize(user_id, organization_id, orbit_id, Action.DELETE)
        await self.__repo.delete_gone_flows()
        flow = await self._get_visible_flow(user_id, orbit_id, flow_id)
        # Refuses with "not found" anyone but the session's owner.
        await self._live_sessions.end_session(
            user_id, organization_id, orbit_id, flow.session.id
        )
        await self.__repo.delete_flow(flow.id, flow.session.id)
