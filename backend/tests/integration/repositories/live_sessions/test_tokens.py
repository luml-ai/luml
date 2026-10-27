import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from luml.models import LiveSessionOrm, LiveSessionTokenOrm
from luml.repositories.live_session_tokens import (
    LiveSessionTokenRepository,
    hash_session_token,
)
from luml.repositories.live_sessions import LiveSessionRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionTokenCreate,
    SessionTokenKind,
)
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.support.live_sessions import start_session
from tests.support.seeds import OrbitFixtureData

GRANT_LIFETIME = timedelta(hours=12)


async def _issue(
    repo: LiveSessionTokenRepository,
    live_session: LiveSession,
    kind: SessionTokenKind = SessionTokenKind.VIEW,
    lifetime: timedelta = timedelta(minutes=5),
    destination: str | None = None,
) -> str:
    return await repo.issue_token(
        LiveSessionTokenCreate(
            kind=kind,
            session_id=live_session.id,
            user_id=live_session.user_id,
            expires_at=datetime.now(UTC) + lifetime,
            destination=destination,
        )
    )


async def _expire(engine: AsyncEngine, token: str, ago: timedelta) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(LiveSessionTokenOrm)
            .where(LiveSessionTokenOrm.token_hash == hash_session_token(token))
            .values(expires_at=datetime.now(UTC) - ago)
        )
        await session.commit()


async def _stored_hashes(engine: AsyncEngine) -> set[str]:
    async with AsyncSession(engine) as session:
        return set(await session.scalars(select(LiveSessionTokenOrm.token_hash)))


class TestLiveSessionTokenRepository:
    async def test_only_the_hash_of_a_token_is_stored(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)

        token = await _issue(
            token_repository, live_session, destination="/experiments/42"
        )

        async with AsyncSession(data.engine) as session:
            rows = (
                await session.execute(text("SELECT * FROM live_session_tokens"))
            ).all()
        assert len(rows) == 1
        assert all(token not in str(value) for value in rows[0])
        assert await _stored_hashes(data.engine) == {hash_session_token(token)}

    async def test_a_token_is_found_with_its_session(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        token = await _issue(
            token_repository, live_session, destination="/experiments/42"
        )

        found = await token_repository.get_token_with_session(token)

        assert found is not None
        stored, owner = found
        assert (stored.kind, stored.session_id, stored.user_id) == (
            SessionTokenKind.VIEW,
            live_session.id,
            data.user.id,
        )
        assert (stored.launched_at, stored.destination) == (None, "/experiments/42")
        assert owner.id == live_session.id
        assert await token_repository.get_token_with_session("unknown") is None

    async def test_expired_tokens_are_removed_when_a_token_is_issued(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        expired = await _issue(token_repository, live_session, SessionTokenKind.EXPOSE)
        valid = await _issue(token_repository, live_session)
        await _expire(data.engine, expired, timedelta(hours=1))

        fresh = await _issue(token_repository, live_session, SessionTokenKind.EXPOSE)

        assert await _stored_hashes(data.engine) == {
            hash_session_token(valid),
            hash_session_token(fresh),
        }

    async def test_expired_tokens_are_removed_when_a_token_is_launched(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        expired = await _issue(token_repository, live_session)
        launched = await _issue(token_repository, live_session)
        await _expire(data.engine, expired, timedelta(hours=1))
        found = await token_repository.get_token_with_session(launched)
        assert found is not None

        await token_repository.launch_view_token(
            found[0].id, datetime.now(UTC) + GRANT_LIFETIME
        )

        assert await _stored_hashes(data.engine) == {hash_session_token(launched)}

    async def test_a_launch_turns_a_view_token_into_a_grant_once(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        token = await _issue(
            token_repository, live_session, destination="/experiments/42"
        )
        found = await token_repository.get_token_with_session(token)
        assert found is not None
        grant_expires_at = datetime.now(UTC) + GRANT_LIFETIME

        grant = await token_repository.launch_view_token(found[0].id, grant_expires_at)
        second = await token_repository.launch_view_token(found[0].id, grant_expires_at)

        assert grant is not None
        assert grant.id == found[0].id
        assert grant.launched_at is not None
        assert grant.expires_at == grant_expires_at
        assert grant.destination == "/experiments/42"
        assert second is None
        by_id = await token_repository.get_grant_with_session(grant.id)
        assert by_id is not None
        assert by_id[0] == grant
        assert by_id[1].id == live_session.id

    async def test_of_two_concurrent_launches_exactly_one_succeeds(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        found = await token_repository.get_token_with_session(
            await _issue(token_repository, live_session)
        )
        assert found is not None
        grant_expires_at = datetime.now(UTC) + GRANT_LIFETIME

        results = await asyncio.gather(
            token_repository.launch_view_token(found[0].id, grant_expires_at),
            token_repository.launch_view_token(found[0].id, grant_expires_at),
        )

        assert sum(result is not None for result in results) == 1

    @pytest.mark.parametrize(
        ("kind", "lifetime"),
        [
            (SessionTokenKind.EXPOSE, timedelta(minutes=10)),
            (SessionTokenKind.VIEW, -timedelta(seconds=1)),
        ],
        ids=["expose", "expired-view"],
    )
    async def test_only_an_unexpired_view_token_launches(
        self,
        token_repository: LiveSessionTokenRepository,
        seeded_orbit: OrbitFixtureData,
        kind: SessionTokenKind,
        lifetime: timedelta,
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        found = await token_repository.get_token_with_session(
            await _issue(token_repository, live_session, kind, lifetime)
        )
        assert found is not None

        launched = await token_repository.launch_view_token(
            found[0].id, datetime.now(UTC) + GRANT_LIFETIME
        )

        assert launched is None

    async def test_viewer_activity_is_recorded_on_the_session(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        live_session = await start_session(data)
        assert live_session.last_viewer_activity_at is None
        before = datetime.now(UTC)

        await repository.record_viewer_activity(live_session.id)

        async with AsyncSession(data.engine) as session:
            recorded = await session.get(LiveSessionOrm, live_session.id)
        assert recorded is not None
        assert recorded.last_viewer_activity_at is not None
        assert recorded.last_viewer_activity_at >= before
