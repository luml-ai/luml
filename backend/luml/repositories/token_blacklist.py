import time

from sqlalchemy import delete, select

from luml.models import TokenBlackListOrm
from luml.repositories.base import RepositoryBase


class TokenBlackListRepository(RepositoryBase):
    async def add_token(self, token: str, expire_at: int) -> None:
        async with self._get_session() as session:
            token_black_list = TokenBlackListOrm(token=token, expire_at=expire_at)
            session.add(token_black_list)
            await session.commit()
        await self.delete_expired_tokens()

    async def is_token_blacklisted(self, token: str) -> bool:
        async with self._get_session() as session:
            result = await session.execute(
                select(TokenBlackListOrm).filter(TokenBlackListOrm.token == token)
            )
            return result.scalar_one_or_none() is not None

    async def delete_expired_tokens(self) -> None:
        async with self._get_session() as session:
            await session.execute(
                delete(TokenBlackListOrm).filter(
                    TokenBlackListOrm.expire_at < int(time.time())
                )
            )
            await session.commit()
