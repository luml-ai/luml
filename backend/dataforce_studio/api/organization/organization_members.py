from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.organizations import OrganizationHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.organization import (
    OrganizationMember,
    OrganizationMemberCreate,
    UpdateOrganizationMember,
)

members_router = APIRouter(
    prefix="/{organization_id}/members",
    dependencies=[Depends(UserAuthentication(["jwt"]))],
    tags=["organization-members"],
)

organization_handler = OrganizationHandler()


@members_router.get("", responses=endpoint_responses)
async def get_organization_members(
    request: Request, organization_id: int
) -> list[OrganizationMember]:
    return await organization_handler.get_organization_members_data(
        request.user.id, organization_id
    )


@members_router.post("", responses=endpoint_responses)
async def add_member_to_organization(
    request: Request,
    organization_id: int,
    member: OrganizationMemberCreate,
) -> OrganizationMember:
    return await organization_handler.add_organization_member(
        request.user.id, organization_id, member
    )


@members_router.patch("/{member_id}", responses=endpoint_responses)
async def update_organization_member(
    request: Request,
    organization_id: int,
    member_id: int,
    member: UpdateOrganizationMember,
) -> OrganizationMember | None:
    return await organization_handler.update_organization_member_by_id(
        request.user.id, organization_id, member_id, member
    )


@members_router.delete(
    "/{member_id}", responses=endpoint_responses, status_code=status.HTTP_204_NO_CONTENT
)
async def remove_organization_member(
    request: Request, organization_id: int, member_id: int
) -> None:
    return await organization_handler.delete_organization_member_by_id(
        request.user.id, organization_id, member_id
    )
