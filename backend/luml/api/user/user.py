from fastapi import APIRouter, Depends, Request

from luml.handlers.organizations import OrganizationHandler
from luml.infra.dependencies import UserAuthentication
from luml.schemas.organization import OrganizationSwitcher

user_router = APIRouter(
    prefix="",
    dependencies=[Depends(UserAuthentication(["jwt", "api_key"]))],
    tags=["users-me"],
)

organization_handler = OrganizationHandler()


@user_router.get("/organizations", response_model=list[OrganizationSwitcher])
async def get_available_organizations(request: Request) -> list[OrganizationSwitcher]:
    return await organization_handler.get_user_organizations(request.user.id)
