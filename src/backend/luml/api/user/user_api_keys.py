from fastapi import APIRouter, Depends, Request, status

from luml.handlers.api_keys import APIKeyHandler
from luml.infra.dependencies import UserAuthentication
from luml.schemas.user import APIKeyCreateOut

api_keys_router = APIRouter(
    prefix="/api-keys",
    dependencies=[Depends(UserAuthentication(["jwt"]))],
    tags=["users-me-api-keys"],
)

api_keys_handler = APIKeyHandler()


@api_keys_router.post("", response_model=APIKeyCreateOut)
async def create_user_api_key(request: Request) -> APIKeyCreateOut:
    return await api_keys_handler.create_user_api_key(request.user.id)


@api_keys_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_api_key(request: Request) -> None:
    return await api_keys_handler.delete_user_api_key(request.user.id)
