from fastapi import APIRouter

from lumlflow.handlers.auth import AuthHandler
from lumlflow.schemas.auth import ApiKeyCredentials, HasApiKey

auth_router = APIRouter(prefix="/api/auth")

auth_handler = AuthHandler()


@auth_router.get("/status", response_model=HasApiKey)
async def auth_status() -> HasApiKey:
    return HasApiKey(has_key=auth_handler.has_api_key())


@auth_router.post("/api-key")
async def set_api_key(body: ApiKeyCredentials):
    return auth_handler.set_api_key(body)
