from uuid import uuid4

from luml.handlers.auth import EMAIL_CHANGE_LINK_TTL
from luml.repositories.email_change_requests import (
    KEY_PREFIX,
    EmailChangeRequestRepository,
)
from redis.asyncio import Redis


class TestEmailChangeRequestRepository:
    async def test_only_the_latest_request_is_current(
        self, email_change_requests: EmailChangeRequestRepository
    ) -> None:
        user_id, other_user_id = uuid4(), uuid4()
        first = await email_change_requests.start(user_id)
        assert await email_change_requests.is_current(user_id, first)
        latest = await email_change_requests.start(user_id)
        other = await email_change_requests.start(other_user_id)
        assert not await email_change_requests.is_current(user_id, first)
        assert await email_change_requests.is_current(user_id, latest)
        assert await email_change_requests.is_current(other_user_id, other)
        assert not await email_change_requests.is_current(user_id, other)

    async def test_request_expires_with_the_link(
        self, email_change_requests: EmailChangeRequestRepository, redis_client: Redis
    ) -> None:
        user_id = uuid4()
        await email_change_requests.start(user_id)
        assert (
            0
            < await redis_client.ttl(f"{KEY_PREFIX}{user_id}")
            <= (EMAIL_CHANGE_LINK_TTL)
        )
        assert not await email_change_requests.is_current(uuid4(), uuid4())
