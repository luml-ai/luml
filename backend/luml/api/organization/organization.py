from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.organizations import OrganizationHandler
from luml.handlers.ownership_transfers import OwnershipTransferHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.organization import (
    Organization,
    OrganizationCreateIn,
    OrganizationDetails,
    OrganizationUpdate,
    OwnershipTransfer,
    OwnershipTransferCreate,
)

organization_router = APIRouter(
    prefix="/organizations",
    dependencies=[Depends(UserAuthentication(["jwt"]))],
    tags=["organizations"],
)

organization_handler = OrganizationHandler()


@organization_router.get(
    "/{organization_id}",
    responses=endpoint_responses,
    response_model=OrganizationDetails,
)
async def get_organization_details(
    request: Request, organization_id: UUID
) -> OrganizationDetails:
    return await organization_handler.get_organization(request.user.id, organization_id)


@organization_router.post("", response_model=Organization)
async def create_organization(
    request: Request, organization: OrganizationCreateIn
) -> Organization:
    return await organization_handler.create_organization(request.user.id, organization)


@organization_router.patch(
    "/{organization_id}",
    responses=endpoint_responses,
    response_model=OrganizationDetails,
)
async def update_organization(
    request: Request, organization_id: UUID, organization: OrganizationUpdate
) -> OrganizationDetails:
    return await organization_handler.update_organization(
        request.user.id, organization_id, organization
    )


@organization_router.delete(
    "/{organization_id}",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_organization(request: Request, organization_id: UUID) -> None:
    return await organization_handler.delete_organization(
        request.user.id, organization_id
    )


@organization_router.delete(
    "/{organization_id}/leave",
    responses=endpoint_responses,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def leave_from_organization(request: Request, organization_id: UUID) -> None:
    return await organization_handler.leave_from_organization(
        request.user.id, organization_id
    )


transfer_handler = OwnershipTransferHandler()


@organization_router.post(
    "/{organization_id}/ownership-transfers", response_model=OwnershipTransfer
)
async def request_ownership_transfer(
    request: Request, organization_id: UUID, body: OwnershipTransferCreate
) -> OwnershipTransfer:
    return await transfer_handler.create(
        organization_id, request.user.id, body.member_id
    )


@organization_router.get(
    "/{organization_id}/ownership-transfers/pending",
    response_model=OwnershipTransfer | None,
)
async def pending_ownership_transfer(
    request: Request, organization_id: UUID
) -> OwnershipTransfer | None:
    return await transfer_handler.repository.pending(organization_id, request.user.id)


@organization_router.post(
    "/{organization_id}/ownership-transfers/{transfer_id}/cancel",
    response_model=OwnershipTransfer,
)
async def cancel_ownership_transfer(
    request: Request, organization_id: UUID, transfer_id: UUID
) -> OwnershipTransfer:
    return await transfer_handler.resolve(
        organization_id, transfer_id, request.user.id, "cancelled"
    )


@organization_router.post(
    "/{organization_id}/ownership-transfer-notices/read",
    response_model=list[OwnershipTransfer],
)
async def read_ownership_transfer_notices(
    request: Request, organization_id: UUID
) -> list[OwnershipTransfer]:
    return await transfer_handler.repository.consume_notices(
        organization_id, request.user.id
    )
