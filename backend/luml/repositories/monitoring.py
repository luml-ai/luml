import time
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from luml.models import MonitoringLaunchTokenOrm
from luml.repositories.base import RepositoryBase


class MonitoringLaunchTokenRepository(RepositoryBase):
    async def consume(self, jti: UUID, expire_at: int) -> bool:
        async with self._get_session() as session:
            session.add(MonitoringLaunchTokenOrm(jti=jti, expire_at=expire_at))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
        await self.delete_expired_tokens()
        return True

    async def delete_expired_tokens(self) -> None:
        async with self._get_session() as session:
            await session.execute(
                delete(MonitoringLaunchTokenOrm).filter(
                    MonitoringLaunchTokenOrm.expire_at < int(time.time())
                )
            )
            await session.commit()
