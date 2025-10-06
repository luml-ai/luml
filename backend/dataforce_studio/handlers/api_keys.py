import hashlib
import hmac
import secrets
from typing import Any

from dataforce_studio.infra.db import engine
from dataforce_studio.infra.exceptions import UserAPIKeyCreateError
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.user import UpdateUserAPIKey, APIKeyCreateOut, UserOut
from dataforce_studio.settings import config


class APIKeyHandler:
    __user_repository = UserRepository(engine)

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
        return await self.__user_repository.get_user_by_api_key_hash(
            self._get_key_hash(api_key)
        )

    async def create_user_api_key(self, user_id: str) -> APIKeyCreateOut:
        key = self._generate_api_key()

        created_key = await self.__user_repository.create_user_api_key(
            UpdateUserAPIKey(id=user_id, hashed_api_key=self._get_key_hash(key))
        )

        if not created_key:
            raise UserAPIKeyCreateError()

        return APIKeyCreateOut(key=key)

    async def delete_user_api_key(self, user_id: str) -> None:
        await self.__user_repository.delete_api_key_by_user_id(user_id)
