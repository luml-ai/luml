import pytest
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.bucket_secrets import S3BucketSecretCreate
from luml.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)

from tests.conftest import (
    OrbitFixtureData,
    OrbitWithMembersFixtureData,
    OrganizationFixtureData,
)


@pytest.mark.asyncio
async def test_create_orbit(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data.engine,
        data.organization,
        data.bucket_secret,
    )
    repo = OrbitRepository(engine)

    orbit = OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    created_orbit = await repo.create_orbit(organization.id, orbit)

    assert created_orbit
    assert created_orbit.id
    assert created_orbit.name == orbit.name


@pytest.mark.asyncio
async def test_update_orbit(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data.engine,
        data.organization,
        data.bucket_secret,
    )
    repo = OrbitRepository(engine)

    orbit = OrbitCreateIn(name="test orbit", bucket_secret_id=secret.id)
    created_orbit = await repo.create_orbit(organization.id, orbit)

    assert created_orbit

    new_name = created_orbit.name + "updated"
    updated_orbit = await repo.update_orbit(
        created_orbit.id, OrbitUpdate(name=new_name)
    )

    assert updated_orbit
    assert updated_orbit.id == created_orbit.id
    assert updated_orbit.name == new_name


@pytest.mark.asyncio
async def test_attach_bucket_secret(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data.engine,
        data.organization,
        data.bucket_secret,
    )
    repo = OrbitRepository(engine)
    secret_repo = BucketSecretRepository(engine)

    orbit = await repo.create_orbit(
        organization.id, OrbitCreateIn(name="test", bucket_secret_id=secret.id)
    )
    assert orbit

    secret = await secret_repo.create_bucket_secret(
        S3BucketSecretCreate(
            organization_id=organization.id,
            endpoint="s3",
            bucket_name="test_attach_bucket_secret",
            region="us-east-1",
        )
    )
    assert secret

    updated = await repo.update_orbit(
        orbit.id, OrbitUpdate(name=orbit.name, bucket_secret_id=secret.id)
    )

    assert updated
    assert updated.bucket_secret_id == secret.id


@pytest.mark.asyncio
async def test_delete_orbit(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = OrbitRepository(data.engine)
    orbit = data.orbit

    await repo.delete_orbit(orbit.id)
    fetched_orbit = await repo.get_orbit_simple(orbit.id, orbit.organization_id)

    assert fetched_orbit is None


@pytest.mark.asyncio
async def test_get_orbit(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = OrbitRepository(data.engine)
    orbit = data.orbit

    fetched_orbit = await repo.get_orbit(orbit.id, orbit.organization_id)

    assert fetched_orbit
    assert isinstance(fetched_orbit, OrbitDetails)
    assert fetched_orbit.id == orbit.id
    assert fetched_orbit.name == orbit.name
    assert fetched_orbit.organization_id == orbit.organization_id


@pytest.mark.asyncio
async def test_get_organization_orbits(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    engine, organization, secret = (
        data.engine,
        data.organization,
        data.bucket_secret,
    )
    repo = OrbitRepository(engine)

    for i in range(5):
        await repo.create_orbit(
            organization.id,
            OrbitCreateIn(name=f"orbit #{i}", bucket_secret_id=secret.id),
        )

    orbits = await repo.get_organization_orbits(organization.id)

    assert orbits
    assert isinstance(orbits, list)
    assert len(orbits) == 5
    assert isinstance(orbits[0], Orbit)


@pytest.mark.asyncio
async def test_get_orbit_members(
    create_orbit_with_members: OrbitWithMembersFixtureData,
) -> None:
    data = create_orbit_with_members
    repo = OrbitRepository(data.engine)
    orbit, members = data.orbit, data.members

    orbit_members = await repo.get_orbit_members(orbit.id)

    assert orbit_members
    assert isinstance(orbit_members, list)
    assert len(orbit_members) == len(members)
    assert isinstance(orbit_members[0], OrbitMember)
    assert orbit_members[0].orbit_id == orbit.id


@pytest.mark.asyncio
async def test_create_orbit_member(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = OrbitRepository(data.engine)
    orbit, user = (
        data.orbit,
        data.user,
    )

    member = OrbitMemberCreate(
        user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER
    )
    created_member = await repo.create_orbit_member(member)

    assert created_member
    assert isinstance(created_member, OrbitMember)


@pytest.mark.asyncio
async def test_update_orbit_member(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = OrbitRepository(data.engine)
    orbit, user = (
        data.orbit,
        data.user,
    )

    member = OrbitMemberCreate(
        user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER
    )
    created_member = await repo.create_orbit_member(member)
    assert created_member

    updated_member = await repo.update_orbit_member(
        UpdateOrbitMember(id=created_member.id, role=OrbitRole.ADMIN)
    )

    assert updated_member
    assert isinstance(updated_member, OrbitMember)
    assert updated_member.role == OrbitRole.ADMIN


@pytest.mark.asyncio
async def test_delete_orbit_member(create_orbit: OrbitFixtureData) -> None:
    data = create_orbit
    repo = OrbitRepository(data.engine)
    orbit, user = (
        data.orbit,
        data.user,
    )

    member = OrbitMemberCreate(
        user_id=user.id, orbit_id=orbit.id, role=OrbitRole.MEMBER
    )
    created_member = await repo.create_orbit_member(member)
    assert created_member

    await repo.delete_orbit_member(created_member.id)

    fetched_member = await repo.get_orbit_member(created_member.id)

    assert fetched_member is None
