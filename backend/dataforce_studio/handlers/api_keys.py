import hashlib
import hmac
import secrets
from typing import Any

from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import (
    APIKeyNotFoundError,
    DatabaseConstraintError,
    UserAPIKeyCreateError,
)
from dataforce_studio.repositories.api_keys import APIKeyRepository
from dataforce_studio.schemas.api_keys import APIKeyCreate, APIKeyCreateOut, APIKeyOut
from dataforce_studio.schemas.user import UserOut
from dataforce_studio.settings import config


class APIKeyHandler:
    __api_key_repository = APIKeyRepository(engine)

    def __init__(
        self,
        secret_key: str = config.AUTH_SECRET_KEY,
        algorithm: Any = hashlib.sha256,  # noqa: ANN401
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm

    def _generate_api_key(self) -> str:
        return f"dfs_{secrets.token_urlsafe(32)}"

    def _get_key_hash(self, key: str) -> str:
        return hmac.new(
            self.secret_key.encode(), key.encode(), self.algorithm
        ).hexdigest()

    def _verify_api_key(self, plain_key: str, hashed_key: str) -> bool:
        return self._get_key_hash(plain_key) == hashed_key

    async def authenticate_api_key(self, api_key: str) -> UserOut | None:
        key = await self.__api_key_repository.get_api_key_by_hash(
            self._get_key_hash(api_key)
        )
        return key.user if key else None

    async def create_user_api_key(self, user_id: int) -> APIKeyCreateOut:
        key = self._generate_api_key()
        try:
            created_key = await self.__api_key_repository.create_api_key(
                APIKeyCreate(user_id=user_id, hash=self._get_key_hash(key))
            )
        except DatabaseConstraintError as error:
            raise UserAPIKeyCreateError() from error

        created_key.key = key
        return created_key

    async def get_user_api_key(self, user_id: int) -> APIKeyOut | None:
        return await self.__api_key_repository.get_api_key_by_user_id(user_id)

    async def delete_user_api_key(self, user_id: int) -> None:
        key = await self.__api_key_repository.get_api_key(user_id)

        if not key:
            raise APIKeyNotFoundError()

        await self.__api_key_repository.delete_api_key_by_user_id(user_id)

    async def regenerate_user_api_key(self, user_id: int) -> APIKeyCreateOut:
        await self.delete_user_api_key(user_id)
        return await self.create_user_api_key(user_id)
