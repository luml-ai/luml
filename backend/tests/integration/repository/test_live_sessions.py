import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from luml.infra.exceptions import OrganizationLimitReachedError
from luml.models import LiveSessionOrm, OrganizationOrm
from luml.repositories.limits import OrganizationResource
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionStatus,
)
from luml.schemas.orbit import OrbitCreateIn, OrbitUpdate
from luml.schemas.organization import OrganizationCreateIn
from luml.schemas.relay import Relay, RelayCreate
from luml.schemas.user import CreateUser
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.conftest import OrbitFixtureData

OWN = OrganizationResource.OWN_RELAY_SESSIONS
MANAGED = OrganizationResource.MANAGED_RELAY_SESSIONS


async def create_relay(
    engine: AsyncEngine, organization_id: uuid.UUID | None, label: str = "lab"
) -> Relay:
    unique = uuid.uuid4().hex[:12]
    return await RelayRepository(engine).create_relay(
        RelayCreate(
            label=label,
            base_domain=f"{unique}.tunnel.example",
            agent_url="wss://tunnel.example/connect",
            organization_id=organization_id,
            token_hash=unique,
        )
    )


async def start_session(
    data: OrbitFixtureData,
    user_id: uuid.UUID | None = None,
    name: str = "run",
    relay: Relay | None = None,
    orbit_id: uuid.UUID | None = None,
) -> LiveSession:
    relay = relay or await create_relay(data.engine, data.organization.id)
    return await LiveSessionRepository(data.engine).create_live_session(
        LiveSessionCreate(
            orbit_id=orbit_id or data.orbit.id,
            user_id=user_id or data.user.id,
            name=name,
            relay_id=relay.id,
        ),
        data.organization.id,
        OWN if relay.organization_id else MANAGED,
    )


async def set_limits(
    engine: AsyncEngine, organization_id: uuid.UUID, **limits: int
) -> None:
    async with AsyncSession(engine) as session:
        await session.execute(
            update(OrganizationOrm)
            .where(OrganizationOrm.id == organization_id)
            .values(**limits)
        )
        await session.commit()


async def set_fields(engine: AsyncEngine, session_id: str, **values: Any) -> None:  # noqa: ANN401
    async with AsyncSession(engine) as session:
        await session.execute(
            update(LiveSessionOrm)
            .where(LiveSessionOrm.id == session_id)
            .values(**values)
        )
        await session.commit()


async def create_other_user(engine: AsyncEngine, template: CreateUser) -> uuid.UUID:
    user_data = template.model_copy()
    user_data.email = f"other_{uuid.uuid4()}@example.com"
    user = await UserRepository(engine).create_user(user_data)
    return user.id


@pytest.mark.asyncio
async def test_create_live_session(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit

    relay = await create_relay(data.engine, data.organization.id)

    session = await start_session(data, name="training run", relay=relay)

    assert re.fullmatch(r"[a-z0-9]+", session.id)
    assert session.orbit_id == data.orbit.id
    assert session.user_id == data.user.id
    assert session.name == "training run"
    assert session.relay_id == relay.id
    assert session.last_heartbeat_at is None
    assert session.ended_at is None
    assert session.status == LiveSessionStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_session_identifiers_differ(create_orbit: OrbitFixtureData) -> None:
    first = await start_session(create_orbit)
    second = await start_session(create_orbit)

    assert first.id != second.id


@pytest.mark.asyncio
async def test_identifier_clash_is_retried(create_orbit: OrbitFixtureData) -> None:
    existing = await start_session(create_orbit)

    with patch(
        "luml.repositories.live_sessions.new_session_id",
        side_effect=[existing.id, "freshid00001"],
    ):
        session = await start_session(create_orbit)

    assert session.id == "freshid00001"


@pytest.mark.asyncio
async def test_identifier_is_never_reused(create_orbit: OrbitFixtureData) -> None:
    existing = await start_session(create_orbit)

    with (
        patch(
            "luml.repositories.live_sessions.new_session_id",
            return_value=existing.id,
        ),
        pytest.raises(IntegrityError),
    ):
        await start_session(create_orbit)


@pytest.mark.asyncio
async def test_get_live_session(create_orbit: OrbitFixtureData) -> None:
    repo = LiveSessionRepository(create_orbit.engine)
    session = await start_session(create_orbit)

    assert await repo.get_live_session(session.id) == session
    assert await repo.get_live_session("missing") is None


@pytest.mark.asyncio
async def test_record_heartbeat(create_orbit: OrbitFixtureData) -> None:
    repo = LiveSessionRepository(create_orbit.engine)
    session = await start_session(create_orbit)

    live = await repo.record_heartbeat(session.id, connected=True)
    assert live is not None
    assert live.last_heartbeat_at is not None
    assert live.status == LiveSessionStatus.LIVE

    disconnected = await repo.record_heartbeat(session.id, connected=False)
    assert disconnected is not None
    assert disconnected.status == LiveSessionStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_heartbeat_after_hour_of_silence_does_not_revive(
    create_orbit: OrbitFixtureData,
) -> None:
    repo = LiveSessionRepository(create_orbit.engine)
    session = await start_session(create_orbit)
    silent_since = datetime.now(UTC) - timedelta(minutes=61)
    await set_fields(
        create_orbit.engine,
        session.id,
        started_at=silent_since,
        last_heartbeat_at=silent_since,
        connected=True,
    )

    result = await repo.record_heartbeat(session.id, connected=True)

    assert result is not None
    assert result.status == LiveSessionStatus.ENDED
    assert result.last_heartbeat_at == silent_since


@pytest.mark.asyncio
async def test_heartbeat_to_ended_session_is_not_recorded(
    create_orbit: OrbitFixtureData,
) -> None:
    repo = LiveSessionRepository(create_orbit.engine)
    session = await start_session(create_orbit)
    await repo.end_live_session(session.id)

    result = await repo.record_heartbeat(session.id, connected=True)

    assert result is not None
    assert result.status == LiveSessionStatus.ENDED
    assert result.last_heartbeat_at is None


@pytest.mark.asyncio
async def test_heartbeat_to_missing_session(create_orbit: OrbitFixtureData) -> None:
    repo = LiveSessionRepository(create_orbit.engine)

    assert await repo.record_heartbeat("missing", connected=True) is None


@pytest.mark.asyncio
async def test_end_live_session(create_orbit: OrbitFixtureData) -> None:
    repo = LiveSessionRepository(create_orbit.engine)
    session = await start_session(create_orbit)
    await repo.record_heartbeat(session.id, connected=True)

    ended = await repo.end_live_session(session.id)
    assert ended is not None
    assert ended.ended_at is not None
    assert ended.status == LiveSessionStatus.ENDED

    ended_again = await repo.end_live_session(session.id)
    assert ended_again is not None
    assert ended_again.ended_at == ended.ended_at
    assert await repo.end_live_session("missing") is None


@pytest.mark.asyncio
async def test_ending_a_silent_session_keeps_its_end_time(
    create_orbit: OrbitFixtureData,
) -> None:
    repo = LiveSessionRepository(create_orbit.engine)
    session = await start_session(create_orbit)
    last_heartbeat = datetime.now(UTC) - timedelta(hours=3)
    await set_fields(
        create_orbit.engine,
        session.id,
        started_at=last_heartbeat,
        last_heartbeat_at=last_heartbeat,
    )

    ended = await repo.end_live_session(session.id)

    assert ended is not None
    assert ended.ended_at == last_heartbeat + timedelta(hours=1)


@pytest.mark.asyncio
async def test_list_contains_only_own_sessions_of_the_orbit(
    create_orbit: OrbitFixtureData, test_user_create: CreateUser
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    other_user_id = await create_other_user(data.engine, test_user_create)
    other_orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="other orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert other_orbit is not None

    first = await start_session(data)
    second = await start_session(data)
    await start_session(data, user_id=other_user_id)
    await start_session(data, name="elsewhere", orbit_id=other_orbit.id)

    sessions = await repo.list_live_sessions(data.orbit.id, data.user.id)

    assert [s.id for s in sessions] == [second.id, first.id]


@pytest.mark.asyncio
async def test_list_drops_sessions_ended_over_a_day_ago(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    now = datetime.now(UTC)
    recent = await start_session(data, name="recent")
    old = await start_session(data, name="old")
    silent_recently = await start_session(data, name="silent recently")
    silent_long_ago = await start_session(data, name="silent long ago")
    await set_fields(data.engine, recent.id, ended_at=now - timedelta(hours=23))
    await set_fields(data.engine, old.id, ended_at=now - timedelta(hours=25))
    await set_fields(
        data.engine,
        silent_recently.id,
        started_at=now - timedelta(hours=30),
        last_heartbeat_at=now - timedelta(hours=24),
    )
    await set_fields(
        data.engine,
        silent_long_ago.id,
        started_at=now - timedelta(hours=30),
        last_heartbeat_at=now - timedelta(hours=26),
    )

    sessions = await repo.list_live_sessions(data.orbit.id, data.user.id)

    assert {s.name for s in sessions} == {"recent", "silent recently"}


@pytest.mark.asyncio
async def test_new_organizations_get_the_default_session_limits(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="fresh org")
    )

    details = await UserRepository(data.engine).get_organization_details(
        organization.id
    )

    assert details is not None
    assert details.managed_relay_sessions_limit == 0
    assert details.own_relay_sessions_limit == 5


@pytest.mark.asyncio
async def test_own_relay_limit_counts_unended_sessions_including_disconnected(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    relay = await create_relay(data.engine, data.organization.id)
    sessions = [await start_session(data, relay=relay) for _ in range(5)]
    two_minutes_ago = datetime.now(UTC) - timedelta(minutes=2)
    await set_fields(
        data.engine,
        sessions[0].id,
        started_at=two_minutes_ago,
        last_heartbeat_at=two_minutes_ago,
        connected=True,
    )
    disconnected = await repo.get_live_session(sessions[0].id)
    assert disconnected is not None
    assert disconnected.status == LiveSessionStatus.DISCONNECTED

    with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
        await repo.check_session_slot(data.organization.id, OWN)
    with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
        await start_session(data, relay=relay)

    for session in sessions:
        stored = await repo.get_live_session(session.id)
        assert stored is not None
        assert stored.status != LiveSessionStatus.ENDED

    await repo.end_live_session(sessions[0].id)
    await repo.check_session_slot(data.organization.id, OWN)
    await start_session(data, relay=relay)


@pytest.mark.asyncio
async def test_ended_and_silent_sessions_free_their_place(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    await set_limits(data.engine, data.organization.id, own_relay_sessions_limit=2)
    ended = await start_session(data)
    silent = await start_session(data)
    await repo.end_live_session(ended.id)
    silent_since = datetime.now(UTC) - timedelta(minutes=61)
    await set_fields(
        data.engine, silent.id, started_at=silent_since, last_heartbeat_at=silent_since
    )

    await start_session(data)
    await start_session(data)

    with pytest.raises(OrganizationLimitReachedError):
        await start_session(data)


@pytest.mark.asyncio
async def test_managed_limit_is_independent_and_zero_by_default(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    managed = await create_relay(data.engine, None, label="eu")
    own = await create_relay(data.engine, data.organization.id)

    with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
        await repo.check_session_slot(data.organization.id, MANAGED)
    with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
        await start_session(data, relay=managed)

    await set_limits(
        data.engine,
        data.organization.id,
        managed_relay_sessions_limit=2,
        own_relay_sessions_limit=1,
    )
    await start_session(data, relay=managed)
    await start_session(data, relay=own)
    await start_session(data, relay=managed)

    with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
        await start_session(data, relay=managed)
    with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
        await start_session(data, relay=own)


@pytest.mark.asyncio
async def test_sessions_on_several_managed_relays_share_the_one_managed_limit(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    eu = await create_relay(data.engine, None, label="eu")
    us = await create_relay(data.engine, None, label="us")
    await set_limits(data.engine, data.organization.id, managed_relay_sessions_limit=2)
    await start_session(data, relay=eu)
    await start_session(data, relay=us)

    with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
        await start_session(data, relay=eu)
    with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
        await start_session(data, relay=us)


@pytest.mark.asyncio
async def test_limits_count_sessions_across_orbits_of_one_organization_only(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    orbits = OrbitRepository(data.engine)
    await set_limits(data.engine, data.organization.id, own_relay_sessions_limit=2)
    second_orbit = await orbits.create_orbit(
        data.organization.id,
        OrbitCreateIn(name="second orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert second_orbit is not None
    other_organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="other org")
    )
    other_orbit = await orbits.create_orbit(
        other_organization.id,
        OrbitCreateIn(name="other orbit", bucket_secret_id=data.bucket_secret.id),
    )
    assert other_orbit is not None
    other_relay = await create_relay(data.engine, other_organization.id)
    await LiveSessionRepository(data.engine).create_live_session(
        LiveSessionCreate(
            orbit_id=other_orbit.id,
            user_id=data.user.id,
            name="elsewhere",
            relay_id=other_relay.id,
        ),
        other_organization.id,
        OWN,
    )

    await start_session(data)
    await start_session(data, orbit_id=second_orbit.id)

    with pytest.raises(OrganizationLimitReachedError):
        await start_session(data)


@pytest.mark.asyncio
async def test_a_session_keeps_its_relay_when_the_orbit_is_reassigned(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    orbits = OrbitRepository(data.engine)
    lab = await create_relay(data.engine, data.organization.id, label="lab")
    eu = await create_relay(data.engine, None, label="eu")
    await set_limits(
        data.engine,
        data.organization.id,
        own_relay_sessions_limit=1,
        managed_relay_sessions_limit=1,
    )
    await orbits.update_orbit(
        data.orbit.id, data.organization.id, OrbitUpdate(relay_id=lab.id)
    )
    session = await start_session(data, relay=lab)

    reassigned = await orbits.update_orbit(
        data.orbit.id, data.organization.id, OrbitUpdate(relay_id=eu.id)
    )

    assert reassigned is not None
    assert reassigned.relay_id == eu.id
    stored = await repo.get_live_session(session.id)
    assert stored is not None
    assert stored.relay_id == lab.id
    with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
        await repo.check_session_slot(data.organization.id, OWN)
    await repo.check_session_slot(data.organization.id, MANAGED)
