import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from luml.models import LiveSessionOrm, LiveSessionTokenOrm
from luml.repositories.live_session_tokens import (
    LiveSessionTokenRepository,
    hash_tunnel_token,
)
from luml.repositories.live_sessions import LiveSessionRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionTokenCreate,
    TunnelTokenKind,
)
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.conftest import OrbitFixtureData
from tests.integration.repository.test_live_sessions import start_session

GRANT_LIFETIME = timedelta(hours=12)


async def issue(
    repo: LiveSessionTokenRepository,
    live_session: LiveSession,
    kind: TunnelTokenKind = TunnelTokenKind.VIEW,
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


async def expire(engine: AsyncEngine, token: str, ago: timedelta) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(LiveSessionTokenOrm)
            .where(LiveSessionTokenOrm.token_hash == hash_tunnel_token(token))
            .values(expires_at=datetime.now(UTC) - ago)
        )
        await session.commit()


async def stored_hashes(engine: AsyncEngine) -> set[str]:
    async with AsyncSession(engine) as session:
        return set(await session.scalars(select(LiveSessionTokenOrm.token_hash)))


@pytest.mark.asyncio
async def test_only_the_hash_of_a_token_is_stored(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)

    token = await issue(repo, live_session, destination="/experiments/42")

    async with AsyncSession(data.engine) as session:
        rows = (await session.execute(text("SELECT * FROM live_session_tokens"))).all()
    assert len(rows) == 1
    assert all(token not in str(value) for value in rows[0])
    assert await stored_hashes(data.engine) == {hash_tunnel_token(token)}


@pytest.mark.asyncio
async def test_a_token_is_found_with_its_session(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)
    token = await issue(repo, live_session, destination="/experiments/42")

    found = await repo.get_token_with_session(token)

    assert found is not None
    stored, owner = found
    assert (stored.kind, stored.session_id, stored.user_id) == (
        TunnelTokenKind.VIEW,
        live_session.id,
        data.user.id,
    )
    assert (stored.launched_at, stored.destination) == (None, "/experiments/42")
    assert owner.id == live_session.id
    assert await repo.get_token_with_session("unknown") is None


@pytest.mark.asyncio
async def test_expired_tokens_are_removed_when_a_token_is_issued(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)
    expired = await issue(repo, live_session, TunnelTokenKind.EXPOSE)
    valid = await issue(repo, live_session)
    await expire(data.engine, expired, timedelta(hours=1))

    fresh = await issue(repo, live_session, TunnelTokenKind.EXPOSE)

    assert await stored_hashes(data.engine) == {
        hash_tunnel_token(valid),
        hash_tunnel_token(fresh),
    }


@pytest.mark.asyncio
async def test_expired_tokens_are_removed_when_a_token_is_launched(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)
    expired = await issue(repo, live_session)
    launched = await issue(repo, live_session)
    await expire(data.engine, expired, timedelta(hours=1))
    found = await repo.get_token_with_session(launched)
    assert found is not None

    await repo.launch_view_token(found[0].id, datetime.now(UTC) + GRANT_LIFETIME)

    assert await stored_hashes(data.engine) == {hash_tunnel_token(launched)}


@pytest.mark.asyncio
async def test_a_launch_turns_a_view_token_into_a_grant_once(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)
    token = await issue(repo, live_session, destination="/experiments/42")
    found = await repo.get_token_with_session(token)
    assert found is not None
    grant_expires_at = datetime.now(UTC) + GRANT_LIFETIME

    grant = await repo.launch_view_token(found[0].id, grant_expires_at)
    second = await repo.launch_view_token(found[0].id, grant_expires_at)

    assert grant is not None
    assert grant.id == found[0].id
    assert grant.launched_at is not None
    assert grant.expires_at == grant_expires_at
    assert grant.destination == "/experiments/42"
    assert second is None
    by_id = await repo.get_grant_with_session(grant.id)
    assert by_id is not None
    assert by_id[0] == grant
    assert by_id[1].id == live_session.id


@pytest.mark.asyncio
async def test_of_two_concurrent_launches_exactly_one_succeeds(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)
    found = await repo.get_token_with_session(await issue(repo, live_session))
    assert found is not None
    grant_expires_at = datetime.now(UTC) + GRANT_LIFETIME

    results = await asyncio.gather(
        repo.launch_view_token(found[0].id, grant_expires_at),
        repo.launch_view_token(found[0].id, grant_expires_at),
    )

    assert sum(result is not None for result in results) == 1


@pytest.mark.parametrize(
    ("kind", "lifetime"),
    [
        (TunnelTokenKind.EXPOSE, timedelta(minutes=10)),
        (TunnelTokenKind.VIEW, -timedelta(seconds=1)),
    ],
    ids=["expose", "expired-view"],
)
@pytest.mark.asyncio
async def test_only_an_unexpired_view_token_launches(
    create_orbit: OrbitFixtureData, kind: TunnelTokenKind, lifetime: timedelta
) -> None:
    data = create_orbit
    repo = LiveSessionTokenRepository(data.engine)
    live_session = await start_session(data)
    found = await repo.get_token_with_session(
        await issue(repo, live_session, kind, lifetime)
    )
    assert found is not None

    launched = await repo.launch_view_token(
        found[0].id, datetime.now(UTC) + GRANT_LIFETIME
    )

    assert launched is None


@pytest.mark.asyncio
async def test_viewer_activity_is_recorded_on_the_session(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    live_session = await start_session(data)
    assert live_session.last_viewer_activity_at is None
    before = datetime.now(UTC)

    await LiveSessionRepository(data.engine).record_viewer_activity(live_session.id)

    async with AsyncSession(data.engine) as session:
        recorded = await session.get(LiveSessionOrm, live_session.id)
    assert recorded is not None
    assert recorded.last_viewer_activity_at is not None
    assert recorded.last_viewer_activity_at >= before
