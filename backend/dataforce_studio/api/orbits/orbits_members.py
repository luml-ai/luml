from fastapi import APIRouter, Depends, Request

from dataforce_studio.handlers.orbits import OrbitHandler
from dataforce_studio.infra.dependencies import UserAuthentication
from dataforce_studio.infra.endpoint_responses import endpoint_responses
from dataforce_studio.schemas.orbit import (
    OrbitMember,
    OrbitMemberCreate,
    UpdateOrbitMember,
)

orbit_members_router = APIRouter(
    prefix="/{organization_id}/orbits/{orbit_id}/members",
    dependencies=[Depends(UserAuthentication(["jwt"]))],
    tags=["orbits-members"],
)

orbit_handler = OrbitHandler()


@orbit_members_router.get(
    "", responses=endpoint_responses, response_model=list[OrbitMember]
)
async def get_orbit_members(
    request: Request,
    organization_id: int,
    orbit_id: int,
) -> list[OrbitMember]:
    return await orbit_handler.get_orbit_members(
        request.user.id, organization_id, orbit_id
    )


@orbit_members_router.post("", responses=endpoint_responses, response_model=OrbitMember)
async def add_member_to_orbit(
    request: Request, organization_id: int, member: OrbitMemberCreate
) -> OrbitMember:
    return await orbit_handler.create_orbit_member(
        request.user.id, organization_id, member
    )


@orbit_members_router.patch(
    "/{member_id}", responses=endpoint_responses, response_model=OrbitMember
)
async def update_orbit_member(
    request: Request, organization_id: int, orbit_id: int, member: UpdateOrbitMember
) -> OrbitMember:
    return await orbit_handler.update_orbit_member(
        request.user.id, organization_id, orbit_id, member
    )


@orbit_members_router.delete(
    "/{member_id}", responses=endpoint_responses, status_code=204
)
async def remove_orbit_member(
    request: Request, organization_id: int, orbit_id: int, member_id: int
) -> None:
    return await orbit_handler.delete_orbit_member(
        request.user.id, organization_id, orbit_id, member_id
    )
