from uuid import uuid7

import pytest
from luml.infra.exceptions import OrganizationLimitReachedError
from luml.repositories.platform_admin import PlatformAdminRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import OrganizationCreateIn, OrgRole
from luml.schemas.platform_admin import (
    OrganizationLimitsUpdate,
    OrganizationUsage,
    PlatformAdminUserMembership,
    PlatformAdminUserUpdate,
    PlatformStats,
)
from luml.schemas.user import CreateUser
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.seeds import (
    TEST_ORGANIZATION_LIMITS,
    OrganizationFixtureData,
    SatelliteFixtureData,
)


@pytest.fixture
def repository(engine: AsyncEngine) -> PlatformAdminRepository:
    return PlatformAdminRepository(engine)


class TestPlatformAdminRepository:
    async def test_get_stats_counts_platform_resources_including_personal_organization(
        self,
        repository: PlatformAdminRepository,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        stats = await repository.get_stats()

        assert stats == PlatformStats(
            users=1,
            disabled_users=0,
            users_created_last_30_days=1,
            organizations=2,
            orbits=1,
            satellites=1,
            artifacts=1,
        )

    async def test_search_organizations_reports_enforced_usage(
        self,
        repository: PlatformAdminRepository,
        seeded_satellite: SatelliteFixtureData,
    ) -> None:
        page = await repository.search_organizations(None, limit=10, offset=0)
        usage = {item.id: item.usage for item in page.items}

        assert page.total == 2
        assert usage[seeded_satellite.organization.id] == OrganizationUsage(
            members=1, orbits=1, satellites=1, artifacts=1
        )

    async def test_search_organizations_returns_case_insensitive_name_matches(
        self,
        repository: PlatformAdminRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        matching = await repository.search_organizations("TEST ORG", limit=10, offset=0)
        missing = await repository.search_organizations("acme", limit=10, offset=0)

        assert [item.name for item in matching.items] == ["test org"]
        assert missing.total == 0
        assert missing.items == []

    async def test_search_users_filters_and_counts_memberships(
        self,
        repository: PlatformAdminRepository,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        user_repository = UserRepository(engine)
        await user_repository.create_user(
            new_user.model_copy(update={"email": f"other_{uuid7()}@example.com"})
        )

        everyone = await repository.search_users(None, limit=10, offset=0)
        member = await repository.search_users(
            seeded_organization.user.email[:12], limit=10, offset=0
        )
        wildcard = await repository.search_users("%", limit=10, offset=0)

        assert everyone.total == 2
        assert member.total == 1
        assert member.items[0].id == seeded_organization.user.id
        assert member.items[0].organizations_count == len(
            await user_repository.get_user_organizations(seeded_organization.user.id)
        )
        assert wildcard.total == 0

    async def test_search_users_returns_distinct_users_per_page(
        self,
        repository: PlatformAdminRepository,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        await UserRepository(engine).create_user(
            new_user.model_copy(update={"email": f"other_{uuid7()}@example.com"})
        )

        first = await repository.search_users(None, limit=1, offset=0)
        second = await repository.search_users(None, limit=1, offset=1)

        assert first.total == second.total == 2
        assert first.items[0].id != second.items[0].id

    async def test_update_user_disables_user_reported_by_details_and_stats(
        self,
        repository: PlatformAdminRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        details = await repository.get_user_details(seeded_organization.user.id)
        disabled = await repository.update_user(
            seeded_organization.user.id, PlatformAdminUserUpdate(disabled=True)
        )
        stats = await repository.get_stats()

        assert details is not None
        assert details.organizations_count == len(details.memberships) == 2
        assert (
            PlatformAdminUserMembership(
                organization_id=seeded_organization.organization.id,
                organization_name="test org",
                role=OrgRole.OWNER,
            )
            in details.memberships
        )
        assert disabled is not None
        assert disabled.disabled is True
        assert stats.disabled_users == 1
        assert (
            await repository.update_user(
                uuid7(), PlatformAdminUserUpdate(disabled=True)
            )
            is None
        )
        assert await repository.get_user_details(uuid7()) is None

    async def test_update_organization_limits_changes_only_given_limits(
        self,
        repository: PlatformAdminRepository,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        updated = await repository.update_organization_limits(
            seeded_organization.organization.id,
            OrganizationLimitsUpdate(orbits_limit=7),
        )

        assert updated is not None
        assert updated.limits.orbits_limit == 7
        assert updated.limits.members_limit == TEST_ORGANIZATION_LIMITS["members_limit"]
        assert [(member.user_id, member.role) for member in updated.members] == [
            (seeded_organization.user.id, OrgRole.OWNER)
        ]
        assert (
            await repository.update_organization_limits(
                uuid7(), OrganizationLimitsUpdate(orbits_limit=7)
            )
            is None
        )

    async def test_update_user_raised_organizations_limit_is_enforced(
        self,
        repository: PlatformAdminRepository,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        user_repository = UserRepository(engine)
        memberships = await user_repository.get_user_organizations_membership_count(
            seeded_organization.user.id
        )

        lowered = await repository.update_user(
            seeded_organization.user.id,
            PlatformAdminUserUpdate(organizations_limit=memberships),
        )
        with pytest.raises(OrganizationLimitReachedError):
            await user_repository.create_organization(
                seeded_organization.user.id, OrganizationCreateIn(name="blocked")
            )
        await repository.update_user(
            seeded_organization.user.id,
            PlatformAdminUserUpdate(organizations_limit=memberships + 1),
        )
        created = await user_repository.create_organization(
            seeded_organization.user.id, OrganizationCreateIn(name="allowed")
        )

        assert lowered is not None
        assert lowered.organizations_limit == memberships
        assert created.name == "allowed"
        assert await user_repository.get_user_organizations_limit(
            seeded_organization.user.id
        ) == (memberships + 1)

    async def test_get_user_organizations_limit_returns_default_for_new_user(
        self,
        engine: AsyncEngine,
        seeded_organization: OrganizationFixtureData,
    ) -> None:
        user_repository = UserRepository(engine)

        assert (
            await user_repository.get_user_organizations_limit(
                seeded_organization.user.id
            )
            == 5
        )
        assert await user_repository.get_user_organizations_limit(uuid7()) is None
