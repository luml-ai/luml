import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from luml.infra.exceptions import OrganizationLimitReachedError
from luml.models import FlowOrm
from luml.repositories.flows import FlowRepository
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.flow import Flow, FlowCreate
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionStatus,
    LiveSessionVisibility,
)
from luml.schemas.orbit import OrbitCreateIn
from luml.schemas.user import CreateUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.conftest import OrbitFixtureData
from tests.integration.repository.test_live_sessions import (
    OWN,
    create_other_user,
    create_relay,
    set_fields,
    set_limits,
    start_session,
    unviewed_for,
)


async def expose(
    data: OrbitFixtureData,
    name: str = "training",
    user_id: uuid.UUID | None = None,
    session: LiveSession | None = None,
) -> tuple[Flow, str | None]:
    user_id = user_id or data.user.id
    session = session or await start_session(data, user_id=user_id, label=name)
    return await FlowRepository(data.engine).attach_session(
        FlowCreate(
            orbit_id=data.orbit.id, user_id=user_id, name=name, session_id=session.id
        )
    )


async def count_flows(engine: AsyncEngine) -> int:
    async with AsyncSession(engine) as session:
        return await session.scalar(select(func.count(FlowOrm.id))) or 0


@pytest.mark.asyncio
async def test_a_flow_is_created_with_its_session(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    session = await start_session(data, label="training")

    flow, previous = await expose(data, session=session)

    assert previous is None
    assert (flow.orbit_id, flow.user_id, flow.name) == (
        data.orbit.id,
        data.user.id,
        "training",
    )
    assert flow.session.id == session.id
    assert flow.session.status == LiveSessionStatus.DISCONNECTED
    assert flow.session.started_at == session.started_at
    assert flow.session.last_heartbeat_at is None
    found = await FlowRepository(data.engine).get_flow_by_name(
        data.orbit.id, data.user.id, "training"
    )
    assert found == flow


@pytest.mark.asyncio
async def test_attaching_to_an_existing_name_points_the_flow_at_the_new_session(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    first, _ = await expose(data)
    second_session = await start_session(data, label="training")

    second, previous = await expose(data, session=second_session)

    assert second.id == first.id
    assert second.session.id == second_session.id
    assert previous == first.session.id
    assert await count_flows(data.engine) == 1


@pytest.mark.asyncio
async def test_concurrent_attaches_of_one_name_end_with_one_flow(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    sessions = [await start_session(data, label="training") for _ in range(2)]

    results = await asyncio.gather(
        *(expose(data, session=session) for session in sessions)
    )

    assert await count_flows(data.engine) == 1
    assert len({flow.id for flow, _ in results}) == 1
    # The later attach learns the session the earlier one put there.
    previous = {previous for _, previous in results}
    assert None in previous
    assert previous - {None} <= {session.id for session in sessions}
    flow = await FlowRepository(data.engine).get_flow_by_name(
        data.orbit.id, data.user.id, "training"
    )
    assert flow is not None
    assert flow.session.id in {session.id for session in sessions}


@pytest.mark.asyncio
async def test_list_shows_the_callers_unended_flows_with_their_session(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = FlowRepository(data.engine)
    live, _ = await expose(data, name="live")
    await set_fields(
        data.engine,
        live.session.id,
        last_heartbeat_at=datetime.now(UTC),
        connected=True,
    )
    disconnected, _ = await expose(data, name="disconnected")
    ended, _ = await expose(data, name="ended")
    await set_fields(data.engine, ended.session.id, ended_at=datetime.now(UTC))

    listed = await repo.list_flows(data.orbit.id, data.user.id)

    assert {(flow.name, flow.session.status) for flow in listed} == {
        ("live", LiveSessionStatus.LIVE),
        ("disconnected", LiveSessionStatus.DISCONNECTED),
    }
    [listed_live] = [flow for flow in listed if flow.name == "live"]
    assert listed_live.session.last_heartbeat_at is not None
    assert await repo.get_flow(data.orbit.id, ended.id, data.user.id) is None
    assert await repo.get_flow(data.orbit.id, disconnected.id, data.user.id) == (
        disconnected
    )


@pytest.mark.asyncio
async def test_two_users_share_a_flow_name(
    create_orbit: OrbitFixtureData, test_user_create: CreateUser
) -> None:
    data = create_orbit
    repo = FlowRepository(data.engine)
    other_user_id = await create_other_user(data.engine, test_user_create)

    mine, _ = await expose(data)
    theirs, _ = await expose(data, user_id=other_user_id)

    assert mine.id != theirs.id
    assert await count_flows(data.engine) == 2
    assert [f.id for f in await repo.list_flows(data.orbit.id, data.user.id)] == [
        mine.id
    ]
    assert [f.id for f in await repo.list_flows(data.orbit.id, other_user_id)] == [
        theirs.id
    ]


@pytest.mark.asyncio
async def test_a_flow_is_seen_only_through_its_session(
    create_orbit: OrbitFixtureData, test_user_create: CreateUser
) -> None:
    data = create_orbit
    repo = FlowRepository(data.engine)
    other_user_id = await create_other_user(data.engine, test_user_create)
    flow, _ = await expose(data)

    assert await repo.list_flows(data.orbit.id, other_user_id) == []
    assert await repo.get_flow(data.orbit.id, flow.id, other_user_id) is None


@pytest.mark.asyncio
async def test_a_flow_is_not_found_through_another_orbit(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = FlowRepository(data.engine)
    flow, _ = await expose(data)

    other_orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(name="other", bucket_secret_id=data.bucket_secret.id),
    )
    assert other_orbit is not None

    assert await repo.list_flows(other_orbit.id, data.user.id) == []
    assert await repo.get_flow(other_orbit.id, flow.id, data.user.id) is None


@pytest.mark.asyncio
async def test_gone_flows_are_deleted_and_their_names_freed(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = FlowRepository(data.engine)
    now = datetime.now(UTC)
    ended, _ = await expose(data, name="ended")
    await set_fields(data.engine, ended.session.id, ended_at=now)
    silent, _ = await expose(data, name="silent")
    await set_fields(
        data.engine,
        silent.session.id,
        started_at=now - timedelta(hours=3),
        last_heartbeat_at=now - timedelta(hours=1, minutes=1),
    )
    unviewed, _ = await expose(data, name="unviewed")
    await unviewed_for(data.engine, unviewed.session.id, timedelta(days=8))
    disconnected, _ = await expose(data, name="disconnected")
    await set_fields(
        data.engine,
        disconnected.session.id,
        last_heartbeat_at=now - timedelta(minutes=5),
    )

    await repo.delete_gone_flows()

    for name in ("ended", "silent", "unviewed"):
        assert await repo.get_flow_by_name(data.orbit.id, data.user.id, name) is None
    kept = await repo.get_flow_by_name(data.orbit.id, data.user.id, "disconnected")
    assert kept is not None
    assert kept.id == disconnected.id
    # The ended sessions stay listed; only the flows are gone.
    assert await LiveSessionRepository(data.engine).get_live_session(ended.session.id)
    renewed, previous = await expose(data, name="silent")
    assert previous is None
    assert renewed.id != silent.id


@pytest.mark.asyncio
async def test_flows_go_with_their_sessions_after_the_retention(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = FlowRepository(data.engine)
    old, _ = await expose(data, name="old")
    await set_fields(
        data.engine,
        old.session.id,
        started_at=datetime.now(UTC) - timedelta(days=3),
        ended_at=datetime.now(UTC) - timedelta(days=2),
    )

    await start_session(data, label="new")

    assert await repo.get_flow_by_name(data.orbit.id, data.user.id, "old") is None
    assert await count_flows(data.engine) == 0


@pytest.mark.asyncio
async def test_delete_flow_leaves_its_session(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    flow, _ = await expose(data)

    await FlowRepository(data.engine).delete_flow(flow.id)

    assert await count_flows(data.engine) == 0
    assert await LiveSessionRepository(data.engine).get_live_session(flow.session.id)


@pytest.mark.asyncio
async def test_replacing_at_the_limit_counts_the_replaced_session_as_free(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    relay = await create_relay(data.engine, data.organization.id)
    await set_limits(data.engine, data.organization.id, own_relay_sessions_limit=2)
    await start_session(data, relay=relay)
    replaced = await start_session(data, relay=relay)
    with pytest.raises(OrganizationLimitReachedError):
        await repo.check_session_slot(data.organization.id, OWN)

    await repo.check_session_slot(data.organization.id, OWN, replaced.id)
    new = await repo.create_live_session(
        LiveSessionCreate(
            orbit_id=data.orbit.id,
            user_id=data.user.id,
            label="training",
            visibility=LiveSessionVisibility.OWNER,
            relay_id=relay.id,
        ),
        data.organization.id,
        OWN,
        replacing=replaced.id,
    )

    ended = await repo.get_live_session(replaced.id)
    assert ended is not None
    assert ended.status == LiveSessionStatus.ENDED
    assert new.status == LiveSessionStatus.DISCONNECTED
    with pytest.raises(OrganizationLimitReachedError):
        await repo.check_session_slot(data.organization.id, OWN)


@pytest.mark.asyncio
async def test_a_refused_replacing_start_leaves_the_replaced_session_running(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    own = await create_relay(data.engine, data.organization.id)
    managed = await create_relay(data.engine, None, label="eu")
    await set_limits(
        data.engine,
        data.organization.id,
        own_relay_sessions_limit=1,
        managed_relay_sessions_limit=1,
    )
    await start_session(data, relay=own)
    replaced = await start_session(data, relay=managed)

    # The replaced session holds a managed place, which frees no own place.
    with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
        await repo.create_live_session(
            LiveSessionCreate(
                orbit_id=data.orbit.id,
                user_id=data.user.id,
                label="training",
                visibility=LiveSessionVisibility.OWNER,
                relay_id=own.id,
            ),
            data.organization.id,
            OWN,
            replacing=replaced.id,
        )

    kept = await repo.get_live_session(replaced.id)
    assert kept is not None
    assert kept.ended_at is None


@pytest.mark.asyncio
async def test_concurrent_replacements_of_one_session_at_the_limit_cannot_exceed_it(
    create_orbit: OrbitFixtureData,
) -> None:
    data = create_orbit
    repo = LiveSessionRepository(data.engine)
    relay = await create_relay(data.engine, data.organization.id)
    await set_limits(data.engine, data.organization.id, own_relay_sessions_limit=1)
    replaced = await start_session(data, relay=relay)

    async def replace() -> LiveSession:
        return await repo.create_live_session(
            LiveSessionCreate(
                orbit_id=data.orbit.id,
                user_id=data.user.id,
                label="training",
                visibility=LiveSessionVisibility.OWNER,
                relay_id=relay.id,
            ),
            data.organization.id,
            OWN,
            replacing=replaced.id,
        )

    results = await asyncio.gather(replace(), replace(), return_exceptions=True)

    refused = [r for r in results if isinstance(r, OrganizationLimitReachedError)]
    started = [r for r in results if isinstance(r, LiveSession)]
    assert (len(started), len(refused)) == (1, 1)
    with pytest.raises(OrganizationLimitReachedError):
        await repo.check_session_slot(data.organization.id, OWN)
