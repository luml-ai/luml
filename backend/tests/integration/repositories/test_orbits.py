import random

import pytest
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.orbit_secrets import OrbitSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.schemas.bucket_secrets import S3BucketSecret, S3BucketSecretCreate
from luml.schemas.collections import CollectionCreate, CollectionType
from luml.schemas.orbit import (
    Orbit,
    OrbitCreateIn,
    OrbitDetails,
    OrbitMember,
    OrbitMemberCreate,
    OrbitMemberCreateSimple,
    OrbitRole,
    OrbitUpdate,
    UpdateOrbitMember,
)
from luml.schemas.orbit_secret import OrbitSecretCreate
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.builders import create_sibling_organization
from tests.support.seeds import (
    CollectionFixtureData,
    OrbitFixtureData,
    OrbitWithMembersFixtureData,
    OrganizationFixtureData,
)


@pytest.fixture
def repository(engine: AsyncEngine) -> OrbitRepository:
    return OrbitRepository(engine)


class TestOrbitRepository:
    async def test_create_orbit_returns_created_orbit(
        self,
        repository: OrbitRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        orbit_create = OrbitCreateIn(
            name="test orbit", bucket_secret_id=seeded_organization.bucket_secret.id
        )
        created_orbit = await repository.create_orbit(
            seeded_organization.organization.id, orbit_create
        )

        assert created_orbit
        assert created_orbit.id
        assert created_orbit.name == orbit_create.name

    async def test_update_orbit_renames_orbit_and_keeps_bucket_secret(
        self,
        repository: OrbitRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        created_orbit = await repository.create_orbit(
            seeded_organization.organization.id,
            OrbitCreateIn(
                name="test orbit",
                bucket_secret_id=seeded_organization.bucket_secret.id,
            ),
        )

        assert created_orbit

        new_name = created_orbit.name + "updated"
        updated_orbit = await repository.update_orbit(
            created_orbit.id,
            seeded_organization.organization.id,
            OrbitUpdate(name=new_name),
        )

        assert updated_orbit
        assert updated_orbit.id == created_orbit.id
        assert updated_orbit.name == new_name
        assert updated_orbit.bucket_secret_id == seeded_organization.bucket_secret.id

    async def test_update_orbit_attaches_new_bucket_secret(
        self,
        repository: OrbitRepository,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        created_orbit = await repository.create_orbit(
            seeded_organization.organization.id,
            OrbitCreateIn(
                name="test", bucket_secret_id=seeded_organization.bucket_secret.id
            ),
        )
        assert created_orbit

        new_secret = await BucketSecretRepository(engine).create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=seeded_organization.organization.id,
                endpoint="s3",
                bucket_name="test_attach_bucket_secret",
                region="us-east-1",
            )
        )
        assert isinstance(new_secret, S3BucketSecret)

        updated = await repository.update_orbit(
            created_orbit.id,
            seeded_organization.organization.id,
            OrbitUpdate(name=created_orbit.name, bucket_secret_id=new_secret.id),
        )

        assert updated
        assert updated.bucket_secret_id == new_secret.id

    async def test_delete_orbit_removes_orbit(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        assert (
            await repository.delete_orbit(
                seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
            )
            is True
        )
        fetched_orbit = await repository.get_orbit_simple(
            seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
        )

        assert fetched_orbit is None

    async def test_update_orbit_returns_none_when_organization_differs(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_orbit.engine, seeded_orbit.user.id
        )

        result = await repository.update_orbit(
            seeded_orbit.orbit.id, other_organization.id, OrbitUpdate(name="renamed")
        )

        assert result is None

        untouched = await repository.get_orbit_simple(
            seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
        )
        assert untouched is not None
        assert untouched.name == seeded_orbit.orbit.name

    async def test_delete_orbit_returns_false_when_organization_differs(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_orbit.engine, seeded_orbit.user.id
        )

        assert (
            await repository.delete_orbit(seeded_orbit.orbit.id, other_organization.id)
            is False
        )
        assert (
            await repository.get_orbit_simple(
                seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
            )
            is not None
        )

    async def test_delete_orbit_keeps_cascade_children_when_organization_differs(
        self,
        repository: OrbitRepository,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
    ) -> None:
        orbit_secret_repository = OrbitSecretRepository(engine)
        other_organization = await create_sibling_organization(
            seeded_collection.engine, seeded_collection.user.id
        )

        orbit_secret = await orbit_secret_repository.create_orbit_secret(
            OrbitSecretCreate(
                name="child-secret",
                value="plaintext",
                orbit_id=seeded_collection.orbit.id,
            )
        )

        assert (
            await repository.delete_orbit(
                seeded_collection.orbit.id, other_organization.id
            )
            is False
        )

        assert (
            await CollectionRepository(engine).get_collection(
                seeded_collection.collection.id
            )
            is not None
        )
        assert (
            await orbit_secret_repository.get_orbit_secret(
                orbit_secret.id, seeded_collection.orbit.id
            )
            is not None
        )

    async def test_get_orbit_simple_returns_none_when_organization_differs(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        other_organization = await create_sibling_organization(
            seeded_orbit.engine, seeded_orbit.user.id
        )

        assert (
            await repository.get_orbit_simple(
                seeded_orbit.orbit.id, other_organization.id
            )
            is None
        )
        assert (
            await repository.get_orbit_simple(
                seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
            )
            is not None
        )

    async def test_get_orbit_returns_orbit_details(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        fetched_orbit = await repository.get_orbit(
            seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
        )

        assert fetched_orbit
        assert isinstance(fetched_orbit, OrbitDetails)
        assert fetched_orbit.id == seeded_orbit.orbit.id
        assert fetched_orbit.name == seeded_orbit.orbit.name
        assert fetched_orbit.organization_id == seeded_orbit.orbit.organization_id

    async def test_get_orbit_returns_all_collection_tags(
        self,
        repository: OrbitRepository,
        engine: AsyncEngine,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        collection_repository = CollectionRepository(engine)
        all_tags = ["tag1", "tag2", "tag3", "tag4"]

        for i in range(4):
            collection = CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description=f"Collection {i}",
                name=f"collection-{i}",
                type=CollectionType.MODEL if i % 2 == 0 else CollectionType.DATASET,
                tags=all_tags
                if i == 0
                else random.sample(all_tags, k=random.randint(0, 3)),
            )
            await collection_repository.create_collection(collection)

        fetched_orbit = await repository.get_orbit(
            seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
        )

        assert fetched_orbit
        assert isinstance(fetched_orbit, OrbitDetails)
        assert fetched_orbit.id == seeded_orbit.orbit.id

        assert fetched_orbit.collections_tags is not None
        assert sorted(fetched_orbit.collections_tags) == sorted(all_tags)

    async def test_get_orbit_returns_no_tags_when_orbit_has_no_collections(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        fetched_orbit = await repository.get_orbit(
            seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
        )

        assert fetched_orbit
        assert isinstance(fetched_orbit, OrbitDetails)
        assert fetched_orbit.id == seeded_orbit.orbit.id

        assert fetched_orbit.collections_tags == []

    async def test_get_orbit_returns_no_tags_when_collections_have_no_tags(
        self,
        repository: OrbitRepository,
        engine: AsyncEngine,
        seeded_orbit: OrbitFixtureData,
    ) -> None:
        collection_repository = CollectionRepository(engine)

        for i in range(3):
            collection = CollectionCreate(
                orbit_id=seeded_orbit.orbit.id,
                description=f"Collection {i}",
                name=f"collection-{i}",
                type=CollectionType.MODEL,
                tags=None,
            )
            await collection_repository.create_collection(collection)

        fetched_orbit = await repository.get_orbit(
            seeded_orbit.orbit.id, seeded_orbit.orbit.organization_id
        )

        assert fetched_orbit
        assert isinstance(fetched_orbit, OrbitDetails)
        assert fetched_orbit.id == seeded_orbit.orbit.id

        assert fetched_orbit.collections_tags == []

    async def test_get_organization_orbits_returns_orbits_with_user_roles(
        self,
        repository: OrbitRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        for i in range(5):
            await repository.create_orbit(
                seeded_organization.organization.id,
                OrbitCreateIn(
                    name=f"orbit #{i}",
                    bucket_secret_id=seeded_organization.bucket_secret.id,
                ),
            )
        own_orbit = await repository.create_orbit(
            seeded_organization.organization.id,
            OrbitCreateIn(
                name="own orbit",
                bucket_secret_id=seeded_organization.bucket_secret.id,
                members=[
                    OrbitMemberCreateSimple(
                        user_id=seeded_organization.user.id, role=OrbitRole.ADMIN
                    )
                ],
            ),
        )
        assert own_orbit

        orbits = await repository.get_organization_orbits(
            seeded_organization.organization.id, seeded_organization.user.id
        )

        assert len(orbits) == 6
        assert all(isinstance(orbit, Orbit) for orbit in orbits)
        roles = {orbit.id: orbit.role for orbit in orbits}
        assert roles.pop(own_orbit.id) == OrbitRole.ADMIN
        assert set(roles.values()) == {None}
        assert all(orbit.total_satellites == 0 for orbit in orbits)
        assert next(o for o in orbits if o.id == own_orbit.id).total_members == 1

    async def test_get_orbit_members_returns_all_members(
        self,
        repository: OrbitRepository,
        seeded_orbit_with_members: OrbitWithMembersFixtureData,
    ) -> None:
        orbit_members = await repository.get_orbit_members(
            seeded_orbit_with_members.orbit.id
        )

        assert orbit_members
        assert isinstance(orbit_members, list)
        assert len(orbit_members) == len(seeded_orbit_with_members.members)
        assert isinstance(orbit_members[0], OrbitMember)
        assert orbit_members[0].orbit_id == seeded_orbit_with_members.orbit.id

    async def test_create_orbit_member_returns_member(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        member = OrbitMemberCreate(
            user_id=seeded_orbit.user.id,
            orbit_id=seeded_orbit.orbit.id,
            role=OrbitRole.MEMBER,
        )
        created_member = await repository.create_orbit_member(member)

        assert created_member
        assert isinstance(created_member, OrbitMember)

    async def test_update_orbit_member_changes_role(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        member = OrbitMemberCreate(
            user_id=seeded_orbit.user.id,
            orbit_id=seeded_orbit.orbit.id,
            role=OrbitRole.MEMBER,
        )
        created_member = await repository.create_orbit_member(member)
        assert created_member

        updated_member = await repository.update_orbit_member(
            UpdateOrbitMember(id=created_member.id, role=OrbitRole.ADMIN)
        )

        assert updated_member
        assert isinstance(updated_member, OrbitMember)
        assert updated_member.role == OrbitRole.ADMIN

    async def test_delete_orbit_member_removes_member(
        self, repository: OrbitRepository, seeded_orbit: OrbitFixtureData
    ) -> None:
        member = OrbitMemberCreate(
            user_id=seeded_orbit.user.id,
            orbit_id=seeded_orbit.orbit.id,
            role=OrbitRole.MEMBER,
        )
        created_member = await repository.create_orbit_member(member)
        assert created_member

        await repository.delete_orbit_member(created_member.id)

        fetched_member = await repository.get_orbit_member(created_member.id)

        assert fetched_member is None
