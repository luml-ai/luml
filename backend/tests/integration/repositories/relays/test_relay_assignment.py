import pytest
from luml.handlers.orbits import OrbitHandler
from luml.infra.exceptions import NotFoundError
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.orbit import OrbitCreateIn, OrbitMemberCreate, OrbitRole, OrbitUpdate
from luml.schemas.organization import OrganizationCreateIn, OrgRole
from luml.schemas.user import CreateUser

from tests.support.relays import (
    add_organization_user,
    create_orbit_on_relay,
    create_relay_with_token,
)
from tests.support.seeds import OrganizationFixtureData


class TestRelayAssignment:
    async def test_an_orbit_is_assigned_an_own_or_a_managed_relay_only(
        self,
        seeded_organization: OrganizationFixtureData,
        orbit_handler: OrbitHandler,
    ) -> None:
        data = seeded_organization
        organization_id = data.organization.id
        lab = await create_relay_with_token(
            data.engine, "lab.example", "lab", organization_id=organization_id
        )
        eu = await create_relay_with_token(
            data.engine, "eu.luml.example", "eu", label="eu"
        )
        other_organization = await UserRepository(data.engine).create_organization(
            data.user.id, OrganizationCreateIn(name="other org")
        )
        foreign = await create_relay_with_token(
            data.engine,
            "foreign.example",
            "foreign",
            organization_id=other_organization.id,
        )
        orbit = await create_orbit_on_relay(data, lab)
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
                data.user.id,
                organization_id,
                orbit.id,
                OrbitUpdate(relay_id=foreign.id),
            )
        unchanged = await orbit_handler.get_orbit(
            data.user.id, organization_id, orbit.id
        )
        cleared = await orbit_handler.update_orbit(
            data.user.id, organization_id, orbit.id, OrbitUpdate(relay_id=None)
        )

        assert created_without_relay.relay_id is None
        assert to_lab.relay_id == lab.id
        assert to_eu.relay_id == eu.id
        assert unchanged.relay_id == eu.id
        assert cleared.relay_id is None

    async def test_orbit_members_see_the_assigned_relay_when_listing_orbits(
        self,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        data = seeded_organization
        orbits = OrbitRepository(data.engine)
        member_id = await add_organization_user(data, new_user, OrgRole.MEMBER)
        relay = await create_relay_with_token(
            data.engine, "lab.example", "lab", organization_id=data.organization.id
        )
        orbit = await create_orbit_on_relay(data, relay)
        await orbits.create_orbit_member(
            OrbitMemberCreate(
                user_id=member_id, orbit_id=orbit.id, role=OrbitRole.MEMBER
            )
        )

        listed = await orbits.get_organization_orbits_for_user(
            data.organization.id, member_id
        )

        assert [
            (listed_orbit.id, listed_orbit.relay_id) for listed_orbit in listed
        ] == [(orbit.id, relay.id)]
