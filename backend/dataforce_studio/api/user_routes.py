from fastapi import APIRouter, Depends

from dataforce_studio.api.user.user import user_router
from dataforce_studio.api.user.user_api_keys import api_keys_router
from dataforce_studio.api.user.user_invites import user_invites_router
from dataforce_studio.infra.dependencies import is_user_authenticated

users_routers = APIRouter(
    prefix="/users/me",
    dependencies=[Depends(is_user_authenticated)],
)

users_routers.include_router(api_keys_router)
users_routers.include_router(user_router)
users_routers.include_router(user_invites_router)
