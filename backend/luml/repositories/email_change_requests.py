from uuid import UUID, uuid4

from redis.asyncio import Redis

KEY_PREFIX = "email-change-request:"


class EmailChangeRequestRepository:
    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _key(user_id: UUID) -> str:
        return f"{KEY_PREFIX}{user_id}"

    async def start(self, user_id: UUID) -> UUID:
        request_id = uuid4()
        await self._client.set(
            self._key(user_id), str(request_id), ex=self._ttl_seconds
        )
        return request_id

    async def is_current(self, user_id: UUID, request_id: UUID) -> bool:
        expected = str(request_id)
        current = await self._client.get(self._key(user_id))
        return current in (expected, expected.encode())
