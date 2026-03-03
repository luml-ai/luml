from fastapi import APIRouter

from lumlflow.handlers.auth import AuthHandler
from lumlflow.schemas.auth import HasApiKey, SetApiKey

auth_router = APIRouter(prefix="/api/auth")

auth_handler = AuthHandler()


@auth_router.get("/status", response_model=HasApiKey)
def auth_status() -> HasApiKey:
    return HasApiKey(has_key=auth_handler.has_api_key())


@auth_router.post("/api-key")
def set_api_key(body: SetApiKey):
    return auth_handler.set_api_key(body)
