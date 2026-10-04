import uuid
from datetime import UTC, datetime, timedelta

import pytest
from luml.handlers.orbits import OrbitHandler
from luml.handlers.permissions import PermissionsHandler
from luml.handlers.relays import RelayHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    InsufficientPermissionsError,
    NotFoundError,
    RelayHasUnendedSessionsError,
)
from luml.models import LiveSessionOrm
from luml.repositories.limits import OrganizationResource
from luml.repositories.live_sessions import LiveSessionRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionCreate,
    LiveSessionStatus,
    LiveSessionVisibility,
)
from luml.schemas.orbit import (
    OrbitCreateIn,
    OrbitDetails,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
)
from luml.schemas.organization import (
    OrganizationCreateIn,
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.relay import (
    Relay,
    RelayCreate,
    RelayCreateIn,
    RelayKind,
    RelayStatus,
    RelayUpdateIn,
)
from luml.schemas.user import CreateUser
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from tests.support.seeds import OrganizationFixtureData

TOKEN_HASHER = RelayHandler()


def _relay_create(
    base_domain: str,
    token: str,
    organization_id: uuid.UUID | None = None,
    label: str = "lab",
) -> RelayCreate:
    return RelayCreate(
        label=label,
        base_domain=base_domain,
        agent_url="wss://relay.example/connect",
        organization_id=organization_id,
        token_hash=TOKEN_HASHER.hash_token(token),
    )


async def _create_relay(
    engine: AsyncEngine,
    base_domain: str,
    token: str,
    organization_id: uuid.UUID | None = None,
    label: str = "lab",
) -> Relay:
    return await RelayRepository(engine).create_relay(
        _relay_create(base_domain, token, organization_id, label)
    )


async def _authenticated_relay_id(engine: AsyncEngine, token: str) -> uuid.UUID | None:
    relay = await RelayRepository(engine).get_relay_by_token_hash(
        TOKEN_HASHER.hash_token(token)
    )
    return relay.id if relay else None


async def _add_user(
    data: OrganizationFixtureData, new_user: CreateUser, role: OrgRole
) -> uuid.UUID:
    repo = UserRepository(data.engine)
    user = await repo.create_user(
        new_user.model_copy(update={"email": f"{uuid.uuid4()}@example.com"})
    )
    await repo.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id, organization_id=data.organization.id, role=role
        )
    )
    return user.id


async def _create_orbit(data: OrganizationFixtureData, relay: Relay) -> OrbitDetails:
    orbit = await OrbitRepository(data.engine).create_orbit(
        data.organization.id,
        OrbitCreateIn(
            name=f"orbit {uuid.uuid4().hex[:6]}",
            bucket_secret_id=data.bucket_secret.id,
            relay_id=relay.id,
        ),
    )
    assert orbit is not None
    return orbit


async def _start_session(
    data: OrganizationFixtureData, orbit: OrbitDetails, relay: Relay
) -> LiveSession:
    return await LiveSessionRepository(data.engine).create_live_session(
        LiveSessionCreate(
            orbit_id=orbit.id,
            user_id=data.user.id,
            label="run",
            visibility=LiveSessionVisibility.OWNER,
            relay_id=relay.id,
        ),
        data.organization.id,
        OrganizationResource.OWN_RELAY_SESSIONS,
    )


async def _silence(engine: AsyncEngine, session_id: str, silent_for: timedelta) -> None:
    since = datetime.now(UTC) - silent_for
    async with AsyncSession(engine) as session:
        await session.execute(
            update(LiveSessionOrm)
            .where(LiveSessionOrm.id == session_id)
            .values(started_at=since, last_heartbeat_at=since, connected=True)
        )
        await session.commit()


@pytest.fixture
def relay_handler(
    seeded_organization: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> RelayHandler:
    engine = seeded_organization.engine
    monkeypatch.setattr(
        RelayHandler, "_RelayHandler__relay_repo", RelayRepository(engine)
    )
    monkeypatch.setattr(
        PermissionsHandler,
        "_PermissionsHandler__user_repository",
        UserRepository(engine),
    )
    monkeypatch.setattr(
        PermissionsHandler,
        "_PermissionsHandler__orbits_repository",
        OrbitRepository(engine),
    )
    return RelayHandler()


@pytest.mark.asyncio
async def test_managed_relay_is_created_without_owner_and_usable_by_all(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    other_organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="other org")
    )

    managed = await _create_relay(data.engine, "eu.luml.example", "managed", label="eu")
    own = await _create_relay(
        data.engine, "sessions.example", "own", organization_id=data.organization.id
    )

    assert managed.organization_id is None
    assert managed.kind == RelayKind.MANAGED
    assert managed.status == RelayStatus.ENABLED
    assert managed.online is False
    assert own.kind == RelayKind.OWN

    listed = await repo.list_usable_relays(data.organization.id)
    assert {relay.id for relay in listed} == {managed.id, own.id}

    other_listed = await repo.list_usable_relays(other_organization.id)
    assert [relay.id for relay in other_listed] == [managed.id]
    assert await repo.get_relay(own.id, other_organization.id) is None
    assert await repo.get_relay(managed.id, other_organization.id) is not None


@pytest.mark.asyncio
async def test_several_managed_relays_coexist(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)

    eu = await _create_relay(data.engine, "eu.luml.example", "eu", label="eu")
    us = await _create_relay(data.engine, "us.luml.example", "us", label="us")
    await repo.update_relay(us.id, RelayUpdateIn(status=RelayStatus.DRAINING))

    listed = await repo.list_usable_relays(data.organization.id)

    assert [(relay.id, relay.kind, relay.status) for relay in listed] == [
        (eu.id, RelayKind.MANAGED, RelayStatus.ENABLED),
        (us.id, RelayKind.MANAGED, RelayStatus.DRAINING),
    ]


@pytest.mark.asyncio
async def test_base_domain_is_unique_across_relays_in_lower_case(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    await _create_relay(
        data.engine, "sessions.example", "first", organization_id=data.organization.id
    )

    with pytest.raises(DatabaseConstraintError):
        await repo.create_relay(
            RelayCreate(
                **RelayCreateIn(
                    label="shadow",
                    base_domain="Sessions.Example",
                    agent_url="ws://shadow.example/connect",
                ).model_dump(),
                token_hash=TOKEN_HASHER.hash_token("second"),
            )
        )

    assert len(await repo.list_usable_relays(data.organization.id)) == 1


@pytest.mark.asyncio
async def test_changing_base_domain_to_a_taken_one_is_refused(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    await _create_relay(data.engine, "eu.luml.example", "managed")
    own = await _create_relay(
        data.engine, "sessions.example", "own", organization_id=data.organization.id
    )

    with pytest.raises(DatabaseConstraintError):
        await repo.update_relay(own.id, RelayUpdateIn(base_domain="EU.luml.example"))

    unchanged = await repo.get_relay(own.id)
    assert unchanged is not None
    assert unchanged.base_domain == "sessions.example"


@pytest.mark.asyncio
async def test_rotation_keeps_the_previous_token_for_the_overlap(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "first", organization_id=data.organization.id
    )

    await repo.rotate_token(
        relay.id,
        TOKEN_HASHER.hash_token("second"),
        datetime.now(UTC) + timedelta(minutes=10),
    )

    assert await _authenticated_relay_id(data.engine, "first") == relay.id
    assert await _authenticated_relay_id(data.engine, "second") == relay.id


@pytest.mark.asyncio
async def test_previous_token_is_refused_once_the_overlap_has_passed(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "first", organization_id=data.organization.id
    )

    await repo.rotate_token(
        relay.id,
        TOKEN_HASHER.hash_token("second"),
        datetime.now(UTC) - timedelta(seconds=1),
    )

    assert await _authenticated_relay_id(data.engine, "first") is None
    assert await _authenticated_relay_id(data.engine, "second") == relay.id


@pytest.mark.asyncio
async def test_second_rotation_within_the_overlap_retires_the_first_token(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "first", organization_id=data.organization.id
    )
    overlap_end = datetime.now(UTC) + timedelta(minutes=10)

    await repo.rotate_token(relay.id, TOKEN_HASHER.hash_token("second"), overlap_end)
    await repo.rotate_token(relay.id, TOKEN_HASHER.hash_token("third"), overlap_end)

    assert await _authenticated_relay_id(data.engine, "first") is None
    assert await _authenticated_relay_id(data.engine, "second") == relay.id
    assert await _authenticated_relay_id(data.engine, "third") == relay.id


@pytest.mark.asyncio
async def test_report_records_liveness_connected_agents_and_capabilities(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "first", organization_id=data.organization.id
    )

    capabilities = {
        "sessions": {"version": 1, "api_versions": [1]},
        "custom.replay": {"version": 3},
    }

    await repo.record_report(relay.id, 3, capabilities)

    reported = await repo.get_relay(relay.id)
    assert reported is not None
    assert reported.connected_agents == 3
    assert reported.last_seen_at is not None
    assert reported.online is True
    assert reported.capabilities == capabilities
    assert reported.present_capabilities == ["sessions", "custom.replay"]


@pytest.mark.asyncio
async def test_relay_is_removed(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "first", organization_id=data.organization.id
    )

    assert await repo.delete_relay(relay.id) is True
    assert await repo.get_relay(relay.id) is None
    assert await repo.delete_relay(relay.id) is False


@pytest.mark.asyncio
async def test_own_relays_are_deleted_with_the_organization(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="short-lived org")
    )
    own = await _create_relay(
        data.engine, "sessions.example", "own", organization_id=organization.id
    )
    managed = await _create_relay(data.engine, "eu.luml.example", "managed")

    await UserRepository(data.engine).delete_organization(organization.id)

    assert await repo.get_relay(own.id) is None
    assert await repo.get_relay(managed.id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
async def test_owners_and_admins_manage_own_relays(
    seeded_organization: OrganizationFixtureData,
    new_user: CreateUser,
    relay_handler: RelayHandler,
    role: OrgRole,
) -> None:
    data = seeded_organization
    user_id = (
        data.user.id if role == OrgRole.OWNER else await _add_user(data, new_user, role)
    )
    organization_id = data.organization.id

    created = await relay_handler.create_relay(
        user_id,
        organization_id,
        RelayCreateIn(
            label="lab",
            base_domain="sessions.example",
            agent_url="wss://relay.example/connect",
        ),
    )
    relay_id = created.relay.id
    updated = await relay_handler.update_relay(
        user_id, organization_id, relay_id, RelayUpdateIn(label="lab 2")
    )
    rotated = await relay_handler.rotate_token(user_id, organization_id, relay_id)
    await relay_handler.delete_relay(user_id, organization_id, relay_id)

    assert created.token.startswith("dfsrelay_")
    assert created.relay.kind == RelayKind.OWN
    assert updated.label == "lab 2"
    assert rotated.token.startswith("dfsrelay_")
    assert rotated.token != created.token
    assert await relay_handler.list_relays(user_id, organization_id) == []


@pytest.mark.asyncio
async def test_members_may_list_and_read_relays_but_not_change_them(
    seeded_organization: OrganizationFixtureData,
    new_user: CreateUser,
    relay_handler: RelayHandler,
) -> None:
    data = seeded_organization
    organization_id = data.organization.id
    member_id = await _add_user(data, new_user, OrgRole.MEMBER)
    own = await _create_relay(
        data.engine, "sessions.example", "own", organization_id=organization_id
    )
    managed = await _create_relay(data.engine, "eu.luml.example", "managed")

    listed = await relay_handler.list_relays(member_id, organization_id)
    read = await relay_handler.get_relay(member_id, organization_id, own.id)

    assert {(relay.id, relay.kind) for relay in listed} == {
        (own.id, RelayKind.OWN),
        (managed.id, RelayKind.MANAGED),
    }
    assert read.id == own.id
    with pytest.raises(InsufficientPermissionsError):
        await relay_handler.create_relay(
            member_id,
            organization_id,
            RelayCreateIn(
                label="x", base_domain="x.example", agent_url="ws://x.example"
            ),
        )
    with pytest.raises(InsufficientPermissionsError):
        await relay_handler.update_relay(
            member_id, organization_id, own.id, RelayUpdateIn(label="x")
        )
    with pytest.raises(InsufficientPermissionsError):
        await relay_handler.rotate_token(member_id, organization_id, own.id)
    with pytest.raises(InsufficientPermissionsError):
        await relay_handler.delete_relay(member_id, organization_id, own.id)


@pytest.mark.asyncio
async def test_managed_relay_is_read_only_for_organization_admins(
    seeded_organization: OrganizationFixtureData,
    relay_handler: RelayHandler,
) -> None:
    data = seeded_organization
    organization_id = data.organization.id
    managed = await _create_relay(data.engine, "eu.luml.example", "managed", label="eu")

    for attempt in (
        relay_handler.update_relay(
            data.user.id, organization_id, managed.id, RelayUpdateIn(label="mine")
        ),
        relay_handler.rotate_token(data.user.id, organization_id, managed.id),
        relay_handler.delete_relay(data.user.id, organization_id, managed.id),
    ):
        with pytest.raises(ApplicationError, match="Managed relays are read-only"):
            await attempt

    listed = await relay_handler.list_relays(data.user.id, organization_id)
    assert [(relay.id, relay.kind, relay.label) for relay in listed] == [
        (managed.id, RelayKind.MANAGED, "eu")
    ]
    assert await _authenticated_relay_id(data.engine, "managed") == managed.id


@pytest.mark.asyncio
async def test_handler_refuses_a_taken_base_domain_with_a_conflict(
    seeded_organization: OrganizationFixtureData,
    relay_handler: RelayHandler,
) -> None:
    data = seeded_organization
    await _create_relay(data.engine, "sessions.example", "first")

    with pytest.raises(ApplicationError) as refusal:
        await relay_handler.create_relay(
            data.user.id,
            data.organization.id,
            RelayCreateIn(
                label="lab",
                base_domain="Sessions.Example",
                agent_url="wss://relay.example/connect",
            ),
        )

    assert refusal.value.status_code == 409
    assert "base domain" in refusal.value.message
    listed = await relay_handler.list_relays(data.user.id, data.organization.id)
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_removing_a_relay_with_unended_sessions_is_refused(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    sessions = LiveSessionRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "lab", organization_id=data.organization.id
    )
    orbit = await _create_orbit(data, relay)
    live = await _start_session(data, orbit, relay)
    await sessions.record_heartbeat(live.id, connected=True)
    silent = await _start_session(data, orbit, relay)
    await _silence(data.engine, silent.id, timedelta(minutes=5))

    with pytest.raises(RelayHasUnendedSessionsError) as refusal:
        await repo.delete_relay(relay.id)

    assert refusal.value.status_code == 409
    assert refusal.value.message == (
        "Cannot remove the relay: the relay has 2 sessions that have not ended"
    )
    assert await repo.get_relay(relay.id) is not None

    await repo.update_relay(relay.id, RelayUpdateIn(status=RelayStatus.DRAINING))
    await sessions.end_live_session(live.id)
    await sessions.end_live_session(silent.id)

    assert await repo.delete_relay(relay.id) is True
    unassigned = await OrbitRepository(data.engine).get_orbit_simple(
        orbit.id, data.organization.id
    )
    assert unassigned is not None
    assert unassigned.relay_id is None


@pytest.mark.asyncio
async def test_removing_a_relay_keeps_its_ended_sessions(
    seeded_organization: OrganizationFixtureData,
) -> None:
    data = seeded_organization
    sessions = LiveSessionRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "lab", organization_id=data.organization.id
    )
    orbit = await _create_orbit(data, relay)
    ended = await _start_session(data, orbit, relay)
    await sessions.end_live_session(ended.id)
    silent = await _start_session(data, orbit, relay)
    await _silence(data.engine, silent.id, timedelta(minutes=61))
    unviewed = await _start_session(data, orbit, relay)
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

    assert await RelayRepository(data.engine).delete_relay(relay.id) is True

    listed = await sessions.list_live_sessions(orbit.id, data.user.id)
    assert {session.id for session in listed} == {ended.id, silent.id, unviewed.id}
    for session in listed:
        assert session.status == LiveSessionStatus.ENDED
        assert session.relay_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        RelayUpdateIn(base_domain="moved.example"),
        RelayUpdateIn(agent_url="wss://moved.example/connect"),
    ],
    ids=["base-domain", "agent-address"],
)
async def test_changing_the_address_of_a_relay_with_unended_sessions_is_refused(
    seeded_organization: OrganizationFixtureData,
    change: RelayUpdateIn,
) -> None:
    data = seeded_organization
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "sessions.example", "lab", organization_id=data.organization.id
    )
    orbit = await _create_orbit(data, relay)
    disconnected = await _start_session(data, orbit, relay)

    relabeled = await repo.update_relay(
        relay.id,
        RelayUpdateIn(
            label="lab 2",
            status=RelayStatus.DRAINING,
            base_domain=relay.base_domain,
            agent_url=relay.agent_url,
        ),
    )
    with pytest.raises(RelayHasUnendedSessionsError) as refusal:
        await repo.update_relay(relay.id, change)

    assert relabeled is not None
    assert relabeled.label == "lab 2"
    assert refusal.value.message == (
        "Cannot change the base domain or connection address: the relay has "
        "1 session that has not ended"
    )
    unchanged = await repo.get_relay(relay.id)
    assert unchanged is not None
    assert (unchanged.base_domain, unchanged.agent_url) == (
        relay.base_domain,
        relay.agent_url,
    )

    await LiveSessionRepository(data.engine).end_live_session(disconnected.id)
    moved = await repo.update_relay(relay.id, change)

    assert moved is not None
    assert moved.model_dump(include=change.model_fields_set) == change.model_dump(
        exclude_unset=True
    )


@pytest.fixture
def orbit_handler(
    relay_handler: RelayHandler,
    seeded_organization: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> OrbitHandler:
    engine = seeded_organization.engine
    for attribute, repository in (
        ("__orbits_repository", OrbitRepository(engine)),
        ("__user_repository", UserRepository(engine)),
        ("__relay_repository", RelayRepository(engine)),
    ):
        monkeypatch.setattr(OrbitHandler, f"_OrbitHandler{attribute}", repository)
    return OrbitHandler()


@pytest.mark.asyncio
async def test_an_orbit_is_assigned_an_own_or_a_managed_relay_only(
    seeded_organization: OrganizationFixtureData,
    orbit_handler: OrbitHandler,
) -> None:
    data = seeded_organization
    organization_id = data.organization.id
    lab = await _create_relay(
        data.engine, "lab.example", "lab", organization_id=organization_id
    )
    eu = await _create_relay(data.engine, "eu.luml.example", "eu", label="eu")
    other_organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="other org")
    )
    foreign = await _create_relay(
        data.engine, "foreign.example", "foreign", organization_id=other_organization.id
    )
    orbit = await _create_orbit(data, lab)
    created_without_relay = await orbit_handler.create_organization_orbit(
        data.user.id,
        organization_id,
        OrbitCreateIn(name="plain", bucket_secret_id=data.bucket_secret.id),
    )
    with pytest.raises(NotFoundError, match="Relay not found"):
        await orbit_handler.create_organization_orbit(
            data.user.id,
            organization_id,
            OrbitCreateIn(
                name="foreign",
                bucket_secret_id=data.bucket_secret.id,
                relay_id=foreign.id,
            ),
        )

    to_lab = await orbit_handler.update_orbit(
        data.user.id, organization_id, orbit.id, OrbitUpdate(relay_id=lab.id)
    )
    to_eu = await orbit_handler.update_orbit(
        data.user.id, organization_id, orbit.id, OrbitUpdate(relay_id=eu.id)
    )
    with pytest.raises(NotFoundError, match="Relay not found"):
        await orbit_handler.update_orbit(
            data.user.id, organization_id, orbit.id, OrbitUpdate(relay_id=foreign.id)
        )
    unchanged = await orbit_handler.get_orbit(data.user.id, organization_id, orbit.id)
    cleared = await orbit_handler.update_orbit(
        data.user.id, organization_id, orbit.id, OrbitUpdate(relay_id=None)
    )

    assert created_without_relay.relay_id is None
    assert to_lab.relay_id == lab.id
    assert to_eu.relay_id == eu.id
    assert unchanged.relay_id == eu.id
    assert cleared.relay_id is None


@pytest.mark.asyncio
async def test_orbit_members_see_the_assigned_relay_when_listing_orbits(
    seeded_organization: OrganizationFixtureData,
    new_user: CreateUser,
) -> None:
    data = seeded_organization
    orbits = OrbitRepository(data.engine)
    member_id = await _add_user(data, new_user, OrgRole.MEMBER)
    relay = await _create_relay(
        data.engine, "lab.example", "lab", organization_id=data.organization.id
    )
    orbit = await _create_orbit(data, relay)
    await orbits.create_orbit_member(
        OrbitMemberCreate(user_id=member_id, orbit_id=orbit.id, role=OrbitRole.MEMBER)
    )

    listed = await orbits.get_organization_orbits_for_user(
        data.organization.id, member_id
    )

    assert [(listed_orbit.id, listed_orbit.relay_id) for listed_orbit in listed] == [
        (orbit.id, relay.id)
    ]
