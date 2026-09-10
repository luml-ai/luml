import time

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from luml.models import TokenBlackListOrm
from luml.repositories.base import RepositoryBase


class TokenBlackListRepository(RepositoryBase):
    async def add_token(self, token: str, expire_at: int) -> bool:
        async with self._get_session() as session:
            session.add(TokenBlackListOrm(token=token, expire_at=expire_at))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                await session.execute(
                    update(TokenBlackListOrm)
                    .where(TokenBlackListOrm.token == token)
                    .values(
                        expire_at=func.greatest(TokenBlackListOrm.expire_at, expire_at)
                    )
                )
                await session.commit()
                added = False
            else:
                added = True
        await self.delete_expired_tokens()
        return added

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
