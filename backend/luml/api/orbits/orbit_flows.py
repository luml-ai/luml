from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.flows import FlowHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.flow import Flow, FlowExposeIn, FlowExposeOut

flows_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/flows",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["flows"],
)

flow_handler = FlowHandler()


@flows_router.post("", responses=endpoint_responses, response_model=FlowExposeOut)
async def expose_flow(
    request: Request, organization_id: UUID, orbit_id: UUID, flow: FlowExposeIn
) -> FlowExposeOut:
    return await flow_handler.expose_flow(
        request.user.id, organization_id, orbit_id, flow
    )


@flows_router.get("", responses=endpoint_responses, response_model=list[Flow])
async def list_flows(
    request: Request, organization_id: UUID, orbit_id: UUID
) -> list[Flow]:
    return await flow_handler.list_flows(request.user.id, organization_id, orbit_id)


@flows_router.get("/{flow_id}", responses=endpoint_responses, response_model=Flow)
async def get_flow(
    request: Request, organization_id: UUID, orbit_id: UUID, flow_id: UUID
) -> Flow:
    return await flow_handler.get_flow(
        request.user.id, organization_id, orbit_id, flow_id
    )


@flows_router.delete(
    "/{flow_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def remove_flow(
    request: Request, organization_id: UUID, orbit_id: UUID, flow_id: UUID
) -> None:
    await flow_handler.remove_flow(request.user.id, organization_id, orbit_id, flow_id)
