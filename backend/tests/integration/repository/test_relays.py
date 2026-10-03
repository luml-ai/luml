import uuid
from datetime import UTC, datetime, timedelta

import pytest
from luml.handlers.permissions import PermissionsHandler
from luml.handlers.relays import RelayHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    InsufficientPermissionsError,
)
from luml.repositories.orbits import OrbitRepository
from luml.repositories.relays import RelayRepository
from luml.repositories.users import UserRepository
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
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import OrganizationFixtureData

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
    data: OrganizationFixtureData, test_user_create: CreateUser, role: OrgRole
) -> uuid.UUID:
    repo = UserRepository(data.engine)
    user = await repo.create_user(
        test_user_create.model_copy(update={"email": f"{uuid.uuid4()}@example.com"})
    )
    await repo.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id, organization_id=data.organization.id, role=role
        )
    )
    return user.id


@pytest.fixture
def relay_handler(
    create_organization_with_user: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> RelayHandler:
    engine = create_organization_with_user.engine
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
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    other_organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="other org")
    )

    managed = await _create_relay(data.engine, "eu.luml.example", "managed", label="eu")
    own = await _create_relay(
        data.engine, "tunnel.example", "own", organization_id=data.organization.id
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
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
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
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    await _create_relay(
        data.engine, "tunnel.example", "first", organization_id=data.organization.id
    )

    with pytest.raises(DatabaseConstraintError):
        await repo.create_relay(
            RelayCreate(
                **RelayCreateIn(
                    label="shadow",
                    base_domain="Tunnel.Example",
                    agent_url="ws://shadow.example/connect",
                ).model_dump(),
                token_hash=TOKEN_HASHER.hash_token("second"),
            )
        )

    assert len(await repo.list_usable_relays(data.organization.id)) == 1


@pytest.mark.asyncio
async def test_changing_base_domain_to_a_taken_one_is_refused(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    await _create_relay(data.engine, "eu.luml.example", "managed")
    own = await _create_relay(
        data.engine, "tunnel.example", "own", organization_id=data.organization.id
    )

    with pytest.raises(DatabaseConstraintError):
        await repo.update_relay(own.id, RelayUpdateIn(base_domain="EU.luml.example"))

    unchanged = await repo.get_relay(own.id)
    assert unchanged is not None
    assert unchanged.base_domain == "tunnel.example"


@pytest.mark.asyncio
async def test_rotation_keeps_the_previous_token_for_the_overlap(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "tunnel.example", "first", organization_id=data.organization.id
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
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "tunnel.example", "first", organization_id=data.organization.id
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
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "tunnel.example", "first", organization_id=data.organization.id
    )
    overlap_end = datetime.now(UTC) + timedelta(minutes=10)

    await repo.rotate_token(relay.id, TOKEN_HASHER.hash_token("second"), overlap_end)
    await repo.rotate_token(relay.id, TOKEN_HASHER.hash_token("third"), overlap_end)

    assert await _authenticated_relay_id(data.engine, "first") is None
    assert await _authenticated_relay_id(data.engine, "second") == relay.id
    assert await _authenticated_relay_id(data.engine, "third") == relay.id


@pytest.mark.asyncio
async def test_report_records_liveness_and_connected_agents(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "tunnel.example", "first", organization_id=data.organization.id
    )

    await repo.record_report(relay.id, 3)

    reported = await repo.get_relay(relay.id)
    assert reported is not None
    assert reported.connected_agents == 3
    assert reported.last_seen_at is not None
    assert reported.online is True


@pytest.mark.asyncio
async def test_relay_is_removed(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    relay = await _create_relay(
        data.engine, "tunnel.example", "first", organization_id=data.organization.id
    )

    assert await repo.delete_relay(relay.id) is True
    assert await repo.get_relay(relay.id) is None
    assert await repo.delete_relay(relay.id) is False


@pytest.mark.asyncio
async def test_own_relays_are_deleted_with_the_organization(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = RelayRepository(data.engine)
    organization = await UserRepository(data.engine).create_organization(
        data.user.id, OrganizationCreateIn(name="short-lived org")
    )
    own = await _create_relay(
        data.engine, "tunnel.example", "own", organization_id=organization.id
    )
    managed = await _create_relay(data.engine, "eu.luml.example", "managed")

    await UserRepository(data.engine).delete_organization(organization.id)

    assert await repo.get_relay(own.id) is None
    assert await repo.get_relay(managed.id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
async def test_owners_and_admins_manage_own_relays(
    create_organization_with_user: OrganizationFixtureData,
    test_user_create: CreateUser,
    relay_handler: RelayHandler,
    role: OrgRole,
) -> None:
    data = create_organization_with_user
    user_id = (
        data.user.id
        if role == OrgRole.OWNER
        else await _add_user(data, test_user_create, role)
    )
    organization_id = data.organization.id

    created = await relay_handler.create_relay(
        user_id,
        organization_id,
        RelayCreateIn(
            label="lab",
            base_domain="tunnel.example",
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
    create_organization_with_user: OrganizationFixtureData,
    test_user_create: CreateUser,
    relay_handler: RelayHandler,
) -> None:
    data = create_organization_with_user
    organization_id = data.organization.id
    member_id = await _add_user(data, test_user_create, OrgRole.MEMBER)
    own = await _create_relay(
        data.engine, "tunnel.example", "own", organization_id=organization_id
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
    create_organization_with_user: OrganizationFixtureData,
    relay_handler: RelayHandler,
) -> None:
    data = create_organization_with_user
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
    create_organization_with_user: OrganizationFixtureData,
    relay_handler: RelayHandler,
) -> None:
    data = create_organization_with_user
    await _create_relay(data.engine, "tunnel.example", "first")

    with pytest.raises(ApplicationError) as refusal:
        await relay_handler.create_relay(
            data.user.id,
            data.organization.id,
            RelayCreateIn(
                label="lab",
                base_domain="Tunnel.Example",
                agent_url="wss://relay.example/connect",
            ),
        )

    assert refusal.value.status_code == 409
    assert "base domain" in refusal.value.message
    listed = await relay_handler.list_relays(data.user.id, data.organization.id)
    assert len(listed) == 1
