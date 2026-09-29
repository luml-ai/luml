import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from luml.models import LiveSessionOrm
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionStatus,
)
from luml.schemas.orbit import OrbitCreateIn
from luml.schemas.user import CreateUser
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.conftest import OrbitFixtureData


async def start_session(
    data: OrbitFixtureData, user_id: uuid.UUID | None = None, name: str = "run"
) -> LiveSession:
    return await LiveSessionRepository(data.engine).create_live_session(
        LiveSessionCreate(
            orbit_id=data.orbit.id,
            user_id=user_id or data.user.id,
            name=name,
            relay_id="default",
        )
    )


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

    session = await start_session(data, name="training run")

    assert re.fullmatch(r"[a-z0-9]+", session.id)
    assert session.orbit_id == data.orbit.id
    assert session.user_id == data.user.id
    assert session.name == "training run"
    assert session.relay_id == "default"
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
    await repo.create_live_session(
        LiveSessionCreate(
            orbit_id=other_orbit.id,
            user_id=data.user.id,
            name="elsewhere",
            relay_id="default",
        )
    )

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
