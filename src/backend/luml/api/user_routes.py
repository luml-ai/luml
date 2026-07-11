from fastapi import APIRouter

from luml.api.user.user import user_router
from luml.api.user.user_api_keys import api_keys_router
from luml.api.user.user_invites import user_invites_router

users_routers = APIRouter(
    prefix="/users/me",
)

users_routers.include_router(api_keys_router)
users_routers.include_router(user_router)
users_routers.include_router(user_invites_router)
