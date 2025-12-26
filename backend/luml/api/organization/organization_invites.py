from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from luml.handlers.organizations import OrganizationHandler
from luml.infra.dependencies import UserAuthentication
from luml.infra.endpoint_responses import endpoint_responses
from luml.schemas.organization import (
    CreateOrganizationInviteIn,
    OrganizationInvite,
)

invites_router = APIRouter(
    prefix="/{organization_id}/invitations",
    dependencies=[Depends(UserAuthentication(["jwt"]))],
    tags=["organization-invites"],
)

organization_handler = OrganizationHandler()


@invites_router.get(
    "", responses=endpoint_responses, response_model=list[OrganizationInvite]
)
async def get_organization_invites(
    request: Request, organization_id: UUID
) -> list[OrganizationInvite]:
    return await organization_handler.get_organization_invites(
        request.user.id, organization_id
    )


@invites_router.post(
    "", responses=endpoint_responses, response_model=OrganizationInvite
)
async def create_invite_in_organization(
    request: Request, organization_id: UUID, invite: CreateOrganizationInviteIn
) -> OrganizationInvite:
    return await organization_handler.send_invite(request.user.id, invite)


@invites_router.delete(
    "/{invite_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def cancel_invite_to_organization(
    request: Request, organization_id: UUID, invite_id: UUID
) -> None:
    return await organization_handler.cancel_invite(
        request.user.id, organization_id, invite_id
    )
