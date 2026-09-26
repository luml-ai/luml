from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from starlette.responses import RedirectResponse

from luml.handlers.auth import AuthHandler
from luml.handlers.platform_admin import PlatformAdminHandler
from luml.handlers.platform_admin_auth import (
    PlatformAdminAuthHandler,
    PlatformAdminConfig,
)
from luml.infra.endpoint_responses import endpoint_responses
from luml.infra.exceptions import AuthError
from luml.schemas.platform_admin import (
    CODE_CHALLENGE_PATTERN,
    OrganizationLimitsUpdate,
    PlatformAdmin,
    PlatformAdminOrganizationDetails,
    PlatformAdminOrganizationsPage,
    PlatformAdminToken,
    PlatformAdminTokenRequest,
    PlatformAdminUserDetails,
    PlatformAdminUsersPage,
    PlatformAdminUserUpdate,
    PlatformStats,
)
from luml.settings import config

PLATFORM_ADMIN_PREFIX = "/platform-admin"

platform_admin_config = PlatformAdminConfig.from_settings(config)
platform_admin_auth_handler = PlatformAdminAuthHandler(
    platform_admin_config, AuthHandler(secret_key=config.AUTH_SECRET_KEY)
)
platform_admin_handler = PlatformAdminHandler()


def require_platform_admin(request: Request) -> PlatformAdmin:
    # Only the Authorization header is accepted: the httpOnly session cookie
    # must never be enough to reach admin routes from a browser.
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Platform admin token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return platform_admin_auth_handler.authenticate(token.strip())
    except AuthError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from err


CurrentAdmin = Annotated[PlatformAdmin, Depends(require_platform_admin)]

platform_admin_auth_router = APIRouter(prefix="/auth", tags=["platform-admin-auth"])

platform_admin_router = APIRouter(
    dependencies=[Depends(require_platform_admin)],
    responses=endpoint_responses,
    tags=["platform-admin"],
)


@platform_admin_auth_router.get("/google/login")
async def google_login(
    port: Annotated[int, Query(ge=1024, le=65535)],
    code_challenge: Annotated[str, Query(pattern=CODE_CHALLENGE_PATTERN)],
) -> RedirectResponse:
    return RedirectResponse(
        platform_admin_auth_handler.google_login_url(port, code_challenge)
    )


@platform_admin_auth_router.get("/google/callback")
async def google_callback(
    state: Annotated[str, Query(max_length=4096)],
    code: Annotated[str | None, Query(max_length=4096)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> RedirectResponse:
    return RedirectResponse(
        await platform_admin_auth_handler.google_callback_redirect(code, state, error)
    )


@platform_admin_auth_router.post("/token")
async def issue_token(grant: PlatformAdminTokenRequest) -> PlatformAdminToken:
    return await platform_admin_auth_handler.issue_token(grant)


@platform_admin_auth_router.get("/me", responses=endpoint_responses)
async def get_current_admin(admin: CurrentAdmin) -> PlatformAdmin:
    return admin


@platform_admin_router.get("/stats")
async def get_stats() -> PlatformStats:
    return await platform_admin_handler.get_stats()


@platform_admin_router.get("/users")
async def search_users(
    search: Annotated[str | None, Query(max_length=254)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PlatformAdminUsersPage:
    return await platform_admin_handler.search_users(search, limit, offset)


@platform_admin_router.get("/users/{user_id}")
async def get_user(user_id: UUID) -> PlatformAdminUserDetails:
    return await platform_admin_handler.get_user(user_id)


@platform_admin_router.patch("/users/{user_id}")
async def update_user(
    admin: CurrentAdmin, user_id: UUID, update: PlatformAdminUserUpdate
) -> PlatformAdminUserDetails:
    return await platform_admin_handler.update_user(admin, user_id, update)


@platform_admin_router.get("/organizations")
async def search_organizations(
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PlatformAdminOrganizationsPage:
    return await platform_admin_handler.search_organizations(search, limit, offset)


@platform_admin_router.get("/organizations/{organization_id}")
async def get_organization(organization_id: UUID) -> PlatformAdminOrganizationDetails:
    return await platform_admin_handler.get_organization(organization_id)


@platform_admin_router.patch("/organizations/{organization_id}/limits")
async def update_organization_limits(
    admin: CurrentAdmin, organization_id: UUID, limits: OrganizationLimitsUpdate
) -> PlatformAdminOrganizationDetails:
    return await platform_admin_handler.update_organization_limits(
        admin, organization_id, limits
    )


platform_admin_routers = APIRouter(prefix=PLATFORM_ADMIN_PREFIX)
platform_admin_routers.include_router(platform_admin_auth_router)
platform_admin_routers.include_router(platform_admin_router)
