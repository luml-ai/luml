from fastapi import APIRouter, Depends, Request, status

from luml.handlers.relay_worker import RelayWorkerHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.relay import (
    RelayDescription,
    RelayReportIn,
    SessionTokenValidateIn,
    SessionTokenVerdict,
    ViewerGrantCheckIn,
    ViewerGrantVerdict,
)

relay_worker_router = APIRouter(
    prefix="/relays/v1",
    dependencies=[Depends(UserAuthentication(["relay"]))],
    tags=["relays-worker"],
)

relay_worker_handler = RelayWorkerHandler()


@relay_worker_router.get(
    "/self", responses=endpoint_responses, response_model=RelayDescription
)
async def describe_relay(request: Request) -> RelayDescription:
    return await relay_worker_handler.describe(request.user.id)


@relay_worker_router.post(
    "/tokens/validate",
    responses=endpoint_responses,
    response_model=SessionTokenVerdict,
)
async def validate_session_token(
    request: Request, data: SessionTokenValidateIn
) -> SessionTokenVerdict:
    return await relay_worker_handler.validate_token(request.user.id, data)


@relay_worker_router.post(
    "/grants/check",
    responses=endpoint_responses,
    response_model=ViewerGrantVerdict,
)
async def check_viewer_grant(
    request: Request, data: ViewerGrantCheckIn
) -> ViewerGrantVerdict:
    return await relay_worker_handler.check_grant(request.user.id, data.grant_id)


@relay_worker_router.post(
    "/report",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def report_relay(request: Request, data: RelayReportIn) -> None:
    await relay_worker_handler.report(request.user.id, data)
