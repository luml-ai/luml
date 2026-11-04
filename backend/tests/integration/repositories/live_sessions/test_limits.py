from datetime import UTC, datetime, timedelta

import pytest
from luml.infra.exceptions import OrganizationLimitReachedError
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import (
    LiveSessionCreate,
    LiveSessionStatus,
    LiveSessionVisibility,
)
from luml.schemas.orbit import OrbitCreateIn, OrbitUpdate
from luml.schemas.organization import OrganizationCreateIn

from tests.support.live_sessions import (
    MANAGED,
    OWN,
    create_relay,
    set_fields,
    set_limits,
    start_session,
    unviewed_for,
)
from tests.support.seeds import OrbitFixtureData


class TestLiveSessionLimits:
    async def test_new_organizations_get_the_default_session_limits(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        organization = await UserRepository(data.engine).create_organization(
            data.user.id, OrganizationCreateIn(name="fresh org")
        )

        details = await UserRepository(data.engine).get_organization_details(
            organization.id
        )

        assert details is not None
        assert details.managed_relay_sessions_limit == 0
        assert details.own_relay_sessions_limit == 5

    async def test_own_relay_limit_counts_unended_sessions_including_disconnected(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
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
        disconnected = await repository.get_live_session(sessions[0].id)
        assert disconnected is not None
        assert disconnected.status == LiveSessionStatus.DISCONNECTED

        with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
            await repository.check_session_slot(data.organization.id, OWN)
        with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
            await start_session(data, relay=relay)

        for session in sessions:
            stored = await repository.get_live_session(session.id)
            assert stored is not None
            assert stored.status != LiveSessionStatus.ENDED

        await repository.end_live_session(sessions[0].id)
        await repository.check_session_slot(data.organization.id, OWN)
        await start_session(data, relay=relay)

    async def test_ended_and_silent_sessions_free_their_place(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        await set_limits(data.engine, data.organization.id, own_relay_sessions_limit=2)
        ended = await start_session(data)
        silent = await start_session(data)
        await repository.end_live_session(ended.id)
        silent_since = datetime.now(UTC) - timedelta(minutes=61)
        await set_fields(
            data.engine,
            silent.id,
            started_at=silent_since,
            last_heartbeat_at=silent_since,
        )

        await start_session(data)
        await start_session(data)

        with pytest.raises(OrganizationLimitReachedError):
            await start_session(data)

    async def test_managed_limit_is_independent_and_zero_by_default(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        managed = await create_relay(data.engine, None, label="eu")
        own = await create_relay(data.engine, data.organization.id)

        with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
            await repository.check_session_slot(data.organization.id, MANAGED)
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

    async def test_sessions_on_several_managed_relays_share_the_one_managed_limit(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        eu = await create_relay(data.engine, None, label="eu")
        us = await create_relay(data.engine, None, label="us")
        await set_limits(
            data.engine, data.organization.id, managed_relay_sessions_limit=2
        )
        await start_session(data, relay=eu)
        await start_session(data, relay=us)

        with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
            await start_session(data, relay=eu)
        with pytest.raises(OrganizationLimitReachedError, match="managed relays"):
            await start_session(data, relay=us)

    async def test_limits_count_sessions_across_orbits_of_one_organization_only(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
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
        await repository.create_live_session(
            LiveSessionCreate(
                orbit_id=other_orbit.id,
                user_id=data.user.id,
                label="elsewhere",
                visibility=LiveSessionVisibility.OWNER,
                relay_id=other_relay.id,
            ),
            other_organization.id,
            OWN,
        )

        await start_session(data)
        await start_session(data, orbit_id=second_orbit.id)

        with pytest.raises(OrganizationLimitReachedError):
            await start_session(data)

    async def test_a_session_keeps_its_relay_when_the_orbit_is_reassigned(
        self, repository: LiveSessionRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
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
        stored = await repository.get_live_session(session.id)
        assert stored is not None
        assert stored.relay_id == lab.id
        with pytest.raises(OrganizationLimitReachedError, match="its own relays"):
            await repository.check_session_slot(data.organization.id, OWN)
        await repository.check_session_slot(data.organization.id, MANAGED)

    async def test_a_session_nobody_viewed_frees_its_place_in_the_limit(
        self, seeded_orbit: OrbitFixtureData
    ) -> None:
        data = seeded_orbit
        await set_limits(data.engine, data.organization.id, own_relay_sessions_limit=1)
        unviewed = await start_session(data)
        with pytest.raises(OrganizationLimitReachedError):
            await start_session(data)

        await unviewed_for(data.engine, unviewed.id, timedelta(days=7, minutes=1))

        await start_session(data)
