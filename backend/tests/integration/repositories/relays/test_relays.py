from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from luml.infra.exceptions import DatabaseConstraintError, RelayHasUnendedSessionsError
from luml.models import LiveSessionOrm
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import LiveSessionStatus
from luml.schemas.organization import OrganizationCreateIn
from luml.schemas.relay import (
    RelayCreate,
    RelayCreateIn,
    RelayKind,
    RelayStatus,
    RelayUpdateIn,
)
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.relays import (
    TOKEN_HASHER,
    authenticated_relay_id,
    create_orbit_on_relay,
    create_relay_with_token,
    silence_session,
    start_session_on_relay,
)
from tests.support.seeds import OrganizationFixtureData


class TestRelayRepository:
    async def test_managed_relay_is_created_without_owner_and_usable_by_all(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        other_organization = await UserRepository(data.engine).create_organization(
            data.user.id, OrganizationCreateIn(name="other org")
        )

        managed = await create_relay_with_token(
            data.engine, "eu.luml.example", "managed", label="eu"
        )
        own = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "own",
            organization_id=data.organization.id,
        )

        assert managed.organization_id is None
        assert managed.kind == RelayKind.MANAGED
        assert managed.status == RelayStatus.ENABLED
        assert managed.online is False
        assert own.kind == RelayKind.OWN

        listed = await repository.list_usable_relays(data.organization.id)
        assert {relay.id for relay in listed} == {managed.id, own.id}

        other_listed = await repository.list_usable_relays(other_organization.id)
        assert [relay.id for relay in other_listed] == [managed.id]
        assert await repository.get_relay(own.id, other_organization.id) is None
        assert await repository.get_relay(managed.id, other_organization.id) is not None

    async def test_several_managed_relays_coexist(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization

        eu = await create_relay_with_token(
            data.engine, "eu.luml.example", "eu", label="eu"
        )
        us = await create_relay_with_token(
            data.engine, "us.luml.example", "us", label="us"
        )
        await repository.update_relay(us.id, RelayUpdateIn(status=RelayStatus.DRAINING))

        listed = await repository.list_usable_relays(data.organization.id)

        assert [(relay.id, relay.kind, relay.status) for relay in listed] == [
            (eu.id, RelayKind.MANAGED, RelayStatus.ENABLED),
            (us.id, RelayKind.MANAGED, RelayStatus.DRAINING),
        ]

    async def test_base_domain_is_unique_across_relays_in_lower_case(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        await create_relay_with_token(
            data.engine,
            "sessions.example",
            "first",
            organization_id=data.organization.id,
        )

        with pytest.raises(DatabaseConstraintError):
            await repository.create_relay(
                RelayCreate(
                    **RelayCreateIn(
                        label="shadow",
                        base_domain="Sessions.Example",
                        agent_url="ws://shadow.example/connect",
                    ).model_dump(),
                    token_hash=TOKEN_HASHER.hash_token("second"),
                )
            )

        assert len(await repository.list_usable_relays(data.organization.id)) == 1

    async def test_changing_base_domain_to_a_taken_one_is_refused(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        await create_relay_with_token(data.engine, "eu.luml.example", "managed")
        own = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "own",
            organization_id=data.organization.id,
        )

        with pytest.raises(DatabaseConstraintError):
            await repository.update_relay(
                own.id, RelayUpdateIn(base_domain="EU.luml.example")
            )

        unchanged = await repository.get_relay(own.id)
        assert unchanged is not None
        assert unchanged.base_domain == "sessions.example"

    async def test_rotation_keeps_the_previous_token_for_the_overlap(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "first",
            organization_id=data.organization.id,
        )

        await repository.rotate_token(
            relay.id,
            TOKEN_HASHER.hash_token("second"),
            datetime.now(UTC) + timedelta(minutes=10),
        )

        assert await authenticated_relay_id(data.engine, "first") == relay.id
        assert await authenticated_relay_id(data.engine, "second") == relay.id

    async def test_previous_token_is_refused_once_the_overlap_has_passed(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "first",
            organization_id=data.organization.id,
        )

        await repository.rotate_token(
            relay.id,
            TOKEN_HASHER.hash_token("second"),
            datetime.now(UTC) - timedelta(seconds=1),
        )

        assert await authenticated_relay_id(data.engine, "first") is None
        assert await authenticated_relay_id(data.engine, "second") == relay.id

    async def test_second_rotation_within_the_overlap_retires_the_first_token(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "first",
            organization_id=data.organization.id,
        )
        overlap_end = datetime.now(UTC) + timedelta(minutes=10)

        await repository.rotate_token(
            relay.id, TOKEN_HASHER.hash_token("second"), overlap_end
        )
        await repository.rotate_token(
            relay.id, TOKEN_HASHER.hash_token("third"), overlap_end
        )

        assert await authenticated_relay_id(data.engine, "first") is None
        assert await authenticated_relay_id(data.engine, "second") == relay.id
        assert await authenticated_relay_id(data.engine, "third") == relay.id

    async def test_report_records_liveness_connected_agents_and_capabilities(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "first",
            organization_id=data.organization.id,
        )

        capabilities: dict[str, dict[str, Any]] = {
            "sessions": {"version": 1, "api_versions": [1]},
            "custom.replay": {"version": 3},
        }

        await repository.record_report(relay.id, 3, capabilities)

        reported = await repository.get_relay(relay.id)
        assert reported is not None
        assert reported.connected_agents == 3
        assert reported.last_seen_at is not None
        assert reported.online is True
        assert reported.capabilities == capabilities
        assert reported.present_capabilities == ["sessions", "custom.replay"]

    async def test_relay_is_removed(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "first",
            organization_id=data.organization.id,
        )

        assert await repository.delete_relay(relay.id) is True
        assert await repository.get_relay(relay.id) is None
        assert await repository.delete_relay(relay.id) is False

    async def test_own_relays_are_deleted_with_the_organization(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        organization = await UserRepository(data.engine).create_organization(
            data.user.id, OrganizationCreateIn(name="short-lived org")
        )
        own = await create_relay_with_token(
            data.engine, "sessions.example", "own", organization_id=organization.id
        )
        managed = await create_relay_with_token(
            data.engine, "eu.luml.example", "managed"
        )

        await UserRepository(data.engine).delete_organization(organization.id)

        assert await repository.get_relay(own.id) is None
        assert await repository.get_relay(managed.id) is not None

    async def test_removing_a_relay_with_unended_sessions_is_refused(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        sessions = LiveSessionRepository(data.engine)
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "lab",
            organization_id=data.organization.id,
        )
        orbit = await create_orbit_on_relay(data, relay)
        live = await start_session_on_relay(data, orbit, relay)
        await sessions.record_heartbeat(live.id, connected=True)
        silent = await start_session_on_relay(data, orbit, relay)
        await silence_session(data.engine, silent.id, timedelta(minutes=5))

        with pytest.raises(RelayHasUnendedSessionsError) as refusal:
            await repository.delete_relay(relay.id)

        assert refusal.value.status_code == 409
        assert refusal.value.message == (
            "Cannot remove the relay: the relay has 2 sessions that have not ended"
        )
        assert await repository.get_relay(relay.id) is not None

        await repository.update_relay(
            relay.id, RelayUpdateIn(status=RelayStatus.DRAINING)
        )
        await sessions.end_live_session(live.id)
        await sessions.end_live_session(silent.id)

        assert await repository.delete_relay(relay.id) is True
        unassigned = await OrbitRepository(data.engine).get_orbit_simple(
            orbit.id, data.organization.id
        )
        assert unassigned is not None
        assert unassigned.relay_id is None

    async def test_removing_a_relay_keeps_its_ended_sessions(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        data = seeded_organization
        sessions = LiveSessionRepository(data.engine)
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "lab",
            organization_id=data.organization.id,
        )
        orbit = await create_orbit_on_relay(data, relay)
        ended = await start_session_on_relay(data, orbit, relay)
        await sessions.end_live_session(ended.id)
        silent = await start_session_on_relay(data, orbit, relay)
        await silence_session(data.engine, silent.id, timedelta(minutes=61))
        unviewed = await start_session_on_relay(data, orbit, relay)
        async with AsyncSession(data.engine) as db:
            await db.execute(
                update(LiveSessionOrm)
                .where(LiveSessionOrm.id == unviewed.id)
                .values(
                    started_at=datetime.now(UTC) - timedelta(days=7, hours=2),
                    last_heartbeat_at=datetime.now(UTC),
                    connected=True,
                )
            )
            await db.commit()

        assert await repository.delete_relay(relay.id) is True

        listed = await sessions.list_live_sessions(orbit.id, data.user.id)
        assert {session.id for session in listed} == {
            ended.id,
            silent.id,
            unviewed.id,
        }
        for session in listed:
            assert session.status == LiveSessionStatus.ENDED
            assert session.relay_id is None

    @pytest.mark.parametrize(
        "change",
        [
            RelayUpdateIn(base_domain="moved.example"),
            RelayUpdateIn(agent_url="wss://moved.example/connect"),
        ],
        ids=["base-domain", "agent-address"],
    )
    async def test_changing_the_address_of_a_relay_with_unended_sessions_is_refused(
        self,
        repository: RelayRepository,
        seeded_organization: OrganizationFixtureData,
        change: RelayUpdateIn,
    ) -> None:
        data = seeded_organization
        relay = await create_relay_with_token(
            data.engine,
            "sessions.example",
            "lab",
            organization_id=data.organization.id,
        )
        orbit = await create_orbit_on_relay(data, relay)
        disconnected = await start_session_on_relay(data, orbit, relay)

        relabeled = await repository.update_relay(
            relay.id,
            RelayUpdateIn(
                label="lab 2",
                status=RelayStatus.DRAINING,
                base_domain=relay.base_domain,
                agent_url=relay.agent_url,
            ),
        )
        with pytest.raises(RelayHasUnendedSessionsError) as refusal:
            await repository.update_relay(relay.id, change)

        assert relabeled is not None
        assert relabeled.label == "lab 2"
        assert refusal.value.message == (
            "Cannot change the base domain or connection address: the relay has "
            "1 session that has not ended"
        )
        unchanged = await repository.get_relay(relay.id)
        assert unchanged is not None
        assert (unchanged.base_domain, unchanged.agent_url) == (
            relay.base_domain,
            relay.agent_url,
        )

        await LiveSessionRepository(data.engine).end_live_session(disconnected.id)
        moved = await repository.update_relay(relay.id, change)

        assert moved is not None
        assert moved.model_dump(include=change.model_fields_set) == change.model_dump(
            exclude_unset=True
        )
