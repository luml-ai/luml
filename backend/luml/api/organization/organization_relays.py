from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.relays import RelayHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.relay import Relay, RelayCreateIn, RelayTokenOut, RelayUpdateIn

relays_router = APIRouter(
    prefix="/{organization_id}/relays",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["organizations-relays"],
)

relay_handler = RelayHandler()


@relays_router.get("", responses=endpoint_responses, response_model=list[Relay])
async def list_relays(request: Request, organization_id: UUID) -> list[Relay]:
    return await relay_handler.list_relays(request.user.id, organization_id)


@relays_router.post("", responses=endpoint_responses, response_model=RelayTokenOut)
async def create_relay(
    request: Request, organization_id: UUID, relay: RelayCreateIn
) -> RelayTokenOut:
    return await relay_handler.create_relay(request.user.id, organization_id, relay)


@relays_router.get("/{relay_id}", responses=endpoint_responses, response_model=Relay)
async def get_relay(request: Request, organization_id: UUID, relay_id: UUID) -> Relay:
    return await relay_handler.get_relay(request.user.id, organization_id, relay_id)


@relays_router.patch("/{relay_id}", responses=endpoint_responses, response_model=Relay)
async def update_relay(
    request: Request, organization_id: UUID, relay_id: UUID, relay: RelayUpdateIn
) -> Relay:
    return await relay_handler.update_relay(
        request.user.id, organization_id, relay_id, relay
    )


@relays_router.post(
    "/{relay_id}/rotate-token",
    responses=endpoint_responses,
    response_model=RelayTokenOut,
)
async def rotate_relay_token(
    request: Request, organization_id: UUID, relay_id: UUID
) -> RelayTokenOut:
    return await relay_handler.rotate_token(request.user.id, organization_id, relay_id)


@relays_router.delete(
    "/{relay_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def delete_relay(request: Request, organization_id: UUID, relay_id: UUID) -> None:
    await relay_handler.delete_relay(request.user.id, organization_id, relay_id)
