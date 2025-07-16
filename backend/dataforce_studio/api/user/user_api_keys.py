from fastapi import APIRouter, Depends, Request, status

from dataforce_studio.handlers.api_keys import APIKeyHandler
from dataforce_studio.infra.dependencies import is_user_authenticated
from dataforce_studio.schemas.api_keys import APIKeyCreateOut, APIKeyOut

api_keys_router = APIRouter(
    prefix="/api-keys",
    dependencies=[Depends(is_user_authenticated)],
    tags=["users-me-api-keys"],
)

api_keys_handler = APIKeyHandler()


@api_keys_router.post("", response_model=APIKeyCreateOut)
async def create_user_api_key(request: Request) -> APIKeyCreateOut:
    return await api_keys_handler.create_user_api_key(request.user.id)


@api_keys_router.get("", response_model=APIKeyOut)
async def get_user_api_key(request: Request) -> APIKeyOut | None:
    return await api_keys_handler.get_user_api_key(request.user.id)


@api_keys_router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(request: Request, key_id: int) -> None:
    return await api_keys_handler.delete_user_api_key(request.user.id, key_id)
