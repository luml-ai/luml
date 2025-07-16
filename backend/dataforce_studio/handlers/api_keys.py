import secrets

from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError

from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    APIKeyNotFoundError,
    InsufficientPermissionsError,
    UserAPIKeyCreateError,
)
from dataforce_studio.repositories.api_keys import APIKeyRepository
from dataforce_studio.schemas.api_keys import APIKeyCreate, APIKeyCreateOut, APIKeyOut


class APIKeyHandler:
    __api_key_repository = APIKeyRepository(engine)

    def __init__(self) -> None:
        self.__pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def _generate_api_key(self) -> str:
        return f"dfs_{secrets.token_urlsafe(32)}"

    def _get_key_hash(self, key: str) -> str:
        return self.__pwd_context.hash(key)

    def _verify_api_key(self, plain_key: str, hashed_key: str) -> bool:
        return self.__pwd_context.verify(plain_key, hashed_key)

    async def create_user_api_key(self, user_id: int) -> APIKeyCreateOut:
        try:
            key = self._generate_api_key()

            created_key = await self.__api_key_repository.create_api_key(
                APIKeyCreate(user_id=user_id, key=self._get_key_hash(key))
            )
            created_key.key = key
            return created_key
        except IntegrityError as error:
            raise UserAPIKeyCreateError() from error

    async def get_user_api_key(self, user_id: int) -> APIKeyOut | None:
        return await self.__api_key_repository.get_api_key_by_user_id(user_id)

    async def delete_user_api_key(self, user_id: int, key_id: int) -> None:
        key = await self.__api_key_repository.get_api_key(key_id)

        if not key:
            raise APIKeyNotFoundError()
        if not key.user_id == user_id:
            raise InsufficientPermissionsError("Only your own API key can be deleted.")

        await self.__api_key_repository.delete_api_key(key_id)
