from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.organizations import OrganizationHandler
from luml.handlers.ownership_transfers import OwnershipTransferHandler
from luml.infra.dependencies import UserAuthentication
from luml.schemas.organization import OwnershipTransfer, UserInvite
from luml.schemas.user import DetailResponse

user_invites_router = APIRouter(
    prefix="/invitations",
    tags=["users-me-invites"],
    dependencies=[Depends(UserAuthentication(["jwt"]))],
)

organization_handler = OrganizationHandler()


@user_invites_router.get("", response_model=list[UserInvite])
async def get_user_invites(request: Request) -> list[UserInvite]:
    return await organization_handler.get_user_invites(request.user.email)


@user_invites_router.post("/{invite_id}/accept", response_model=DetailResponse)
async def accept_invite_to_organization(
    request: Request, invite_id: UUID
) -> DetailResponse:
    await organization_handler.accept_invite(
        invite_id, request.user.id, request.user.email
    )
    return DetailResponse(detail="Invitation accepted successfully")


@user_invites_router.post("/{invite_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_invite_to_organization(request: Request, invite_id: UUID) -> None:
    return await organization_handler.reject_invite(invite_id, request.user.email)


transfer_handler = OwnershipTransferHandler()


@user_invites_router.get("/ownership-transfers", response_model=list[OwnershipTransfer])
async def received_ownership_transfers(request: Request) -> list[OwnershipTransfer]:
    return await transfer_handler.repository.list_received(request.user.id)


@user_invites_router.post(
    "/ownership-transfers/{organization_id}/{transfer_id}/accept",
    response_model=OwnershipTransfer,
)
async def accept_ownership_transfer(
    request: Request, organization_id: UUID, transfer_id: UUID
) -> OwnershipTransfer:
    return await transfer_handler.resolve(
        organization_id, transfer_id, request.user.id, "accepted"
    )


@user_invites_router.post(
    "/ownership-transfers/{organization_id}/{transfer_id}/decline",
    response_model=OwnershipTransfer,
)
async def decline_ownership_transfer(
    request: Request, organization_id: UUID, transfer_id: UUID
) -> OwnershipTransfer:
    return await transfer_handler.resolve(
        organization_id, transfer_id, request.user.id, "declined"
    )
