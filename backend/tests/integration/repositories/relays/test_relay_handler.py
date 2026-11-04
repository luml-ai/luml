import pytest
from luml.handlers.relays import RelayHandler
from luml.infra.exceptions import ApplicationError, InsufficientPermissionsError
from luml.schemas.organization import OrgRole
from luml.schemas.relay import RelayCreateIn, RelayKind, RelayUpdateIn
from luml.schemas.user import CreateUser

from tests.support.relays import (
    add_organization_user,
    authenticated_relay_id,
    create_relay_with_token,
)
from tests.support.seeds import OrganizationFixtureData


class TestRelayHandler:
    @pytest.mark.parametrize("role", [OrgRole.ADMIN, OrgRole.OWNER])
    async def test_owners_and_admins_manage_own_relays(
        self,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
        relay_handler: RelayHandler,
        role: OrgRole,
    ) -> None:
        data = seeded_organization
        user_id = (
            data.user.id
            if role == OrgRole.OWNER
            else await add_organization_user(data, new_user, role)
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

    async def test_members_may_list_and_read_relays_but_not_change_them(
        self,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
        relay_handler: RelayHandler,
    ) -> None:
        data = seeded_organization
        organization_id = data.organization.id
        member_id = await add_organization_user(data, new_user, OrgRole.MEMBER)
        own = await create_relay_with_token(
            data.engine, "sessions.example", "own", organization_id=organization_id
        )
        managed = await create_relay_with_token(
            data.engine, "eu.luml.example", "managed"
        )

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

    async def test_managed_relay_is_read_only_for_organization_admins(
        self,
        seeded_organization: OrganizationFixtureData,
        relay_handler: RelayHandler,
    ) -> None:
        data = seeded_organization
        organization_id = data.organization.id
        managed = await create_relay_with_token(
            data.engine, "eu.luml.example", "managed", label="eu"
        )

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
        assert await authenticated_relay_id(data.engine, "managed") == managed.id

    async def test_handler_refuses_a_taken_base_domain_with_a_conflict(
        self,
        seeded_organization: OrganizationFixtureData,
        relay_handler: RelayHandler,
    ) -> None:
        data = seeded_organization
        await create_relay_with_token(data.engine, "sessions.example", "first")

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
