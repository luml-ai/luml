from time import time

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert

from luml.models.auth_rate_limit import AuthRateLimitOrm
from luml.repositories.base import RepositoryBase


class AuthRateLimitRepository(RepositoryBase):
    async def consume(self, limits: dict[str, int]) -> int:
        now = int(time())
        window = now // 60
        retry_after = 0
        async with self._get_session() as session:
            await session.execute(
                delete(AuthRateLimitOrm).where(AuthRateLimitOrm.window < window)
            )
            # stable ordering keeps concurrent requests from locking in opposite order
            for key, limit in sorted(limits.items()):
                statement = (
                    insert(AuthRateLimitOrm)
                    .values(key=key, window=window, attempts=1)
                    .on_conflict_do_update(
                        index_elements=["key", "window"],
                        set_={
                            "attempts": func.least(
                                AuthRateLimitOrm.attempts + 1, limit + 1
                            )
                        },
                    )
                    .returning(AuthRateLimitOrm.attempts)
                )
                attempts = (await session.execute(statement)).scalar_one()
                if attempts > limit:
                    retry_after = 60 - now % 60
            # denied attempts must also count
            await session.commit()
        return retry_after
