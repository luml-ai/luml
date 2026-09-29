from uuid import UUID

from fastapi import APIRouter, Depends, Request

from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionHeartbeatIn,
    LiveSessionHeartbeatOut,
    LiveSessionStartIn,
    LiveSessionStartOut,
    LiveSessionViewTokenOut,
)

live_sessions_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/live-sessions",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["live-sessions"],
)

live_session_handler = LiveSessionHandler()


@live_sessions_router.post(
    "", responses=endpoint_responses, response_model=LiveSessionStartOut
)
async def start_live_session(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    live_session: LiveSessionStartIn,
) -> LiveSessionStartOut:
    return await live_session_handler.start_session(
        request.user.id, organization_id, orbit_id, live_session
    )


@live_sessions_router.get(
    "", responses=endpoint_responses, response_model=list[LiveSession]
)
async def list_live_sessions(
    request: Request, organization_id: UUID, orbit_id: UUID
) -> list[LiveSession]:
    return await live_session_handler.list_sessions(
        request.user.id, organization_id, orbit_id
    )


@live_sessions_router.get(
    "/{session_id}", responses=endpoint_responses, response_model=LiveSession
)
async def get_live_session(
    request: Request, organization_id: UUID, orbit_id: UUID, session_id: str
) -> LiveSession:
    return await live_session_handler.get_session(
        request.user.id, organization_id, orbit_id, session_id
    )


@live_sessions_router.post(
    "/{session_id}/heartbeat",
    responses=endpoint_responses,
    response_model=LiveSessionHeartbeatOut,
)
async def record_live_session_heartbeat(
    request: Request,
    organization_id: UUID,
    orbit_id: UUID,
    session_id: str,
    heartbeat: LiveSessionHeartbeatIn,
) -> LiveSessionHeartbeatOut:
    return await live_session_handler.record_heartbeat(
        request.user.id, organization_id, orbit_id, session_id, heartbeat
    )


@live_sessions_router.post(
    "/{session_id}/view-token",
    responses=endpoint_responses,
    response_model=LiveSessionViewTokenOut,
)
async def issue_live_session_view_token(
    request: Request, organization_id: UUID, orbit_id: UUID, session_id: str
) -> LiveSessionViewTokenOut:
    return await live_session_handler.issue_view_token(
        request.user.id, organization_id, orbit_id, session_id
    )


@live_sessions_router.post(
    "/{session_id}/end", responses=endpoint_responses, response_model=LiveSession
)
async def end_live_session(
    request: Request, organization_id: UUID, orbit_id: UUID, session_id: str
) -> LiveSession:
    return await live_session_handler.end_session(
        request.user.id, organization_id, orbit_id, session_id
    )
