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

from tests.conftest import (
    TEST_ORGANIZATION_LIMITS,
    OrganizationFixtureData,
    SatelliteFixtureData,
)


@pytest.mark.asyncio
async def test_stats_count_platform_resources(
    create_satellite: SatelliteFixtureData,
) -> None:
    repo = PlatformAdminRepository(create_satellite.engine)

    stats = await repo.get_stats()

    # Signing up also creates a personal organization for the user.
    assert stats == PlatformStats(
        users=1,
        disabled_users=0,
        users_created_last_30_days=1,
        organizations=2,
        orbits=1,
        satellites=1,
        artifacts=1,
    )


@pytest.mark.asyncio
async def test_search_organizations_reports_enforced_usage(
    create_satellite: SatelliteFixtureData,
) -> None:
    repo = PlatformAdminRepository(create_satellite.engine)

    page = await repo.search_organizations(None, limit=10, offset=0)
    usage = {item.id: item.usage for item in page.items}

    assert page.total == 2
    assert usage[create_satellite.organization.id] == OrganizationUsage(
        members=1, orbits=1, satellites=1, artifacts=1
    )


@pytest.mark.asyncio
async def test_search_organizations_by_name(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    repo = PlatformAdminRepository(create_organization_with_user.engine)

    matching = await repo.search_organizations("TEST ORG", limit=10, offset=0)
    missing = await repo.search_organizations("acme", limit=10, offset=0)

    assert [item.name for item in matching.items] == ["test org"]
    assert missing.total == 0
    assert missing.items == []


@pytest.mark.asyncio
async def test_search_users_filters_and_counts_memberships(
    create_organization_with_user: OrganizationFixtureData,
    test_user_create: CreateUser,
) -> None:
    data = create_organization_with_user
    repo = PlatformAdminRepository(data.engine)
    await UserRepository(data.engine).create_user(
        test_user_create.model_copy(update={"email": f"other_{uuid7()}@example.com"})
    )

    everyone = await repo.search_users(None, limit=10, offset=0)
    member = await repo.search_users(data.user.email[:12], limit=10, offset=0)
    wildcard = await repo.search_users("%", limit=10, offset=0)

    assert everyone.total == 2
    assert member.total == 1
    assert member.items[0].id == data.user.id
    assert member.items[0].organizations_count == len(
        await UserRepository(data.engine).get_user_organizations(data.user.id)
    )
    assert wildcard.total == 0


@pytest.mark.asyncio
async def test_search_users_paginates(
    create_organization_with_user: OrganizationFixtureData,
    test_user_create: CreateUser,
) -> None:
    data = create_organization_with_user
    repo = PlatformAdminRepository(data.engine)
    await UserRepository(data.engine).create_user(
        test_user_create.model_copy(update={"email": f"other_{uuid7()}@example.com"})
    )

    first = await repo.search_users(None, limit=1, offset=0)
    second = await repo.search_users(None, limit=1, offset=1)

    assert first.total == second.total == 2
    assert first.items[0].id != second.items[0].id


@pytest.mark.asyncio
async def test_user_details_and_disable(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = PlatformAdminRepository(data.engine)

    details = await repo.get_user_details(data.user.id)
    disabled = await repo.update_user(
        data.user.id, PlatformAdminUserUpdate(disabled=True)
    )
    stats = await repo.get_stats()

    assert details is not None
    assert details.organizations_count == len(details.memberships) == 2
    assert (
        PlatformAdminUserMembership(
            organization_id=data.organization.id,
            organization_name="test org",
            role=OrgRole.OWNER,
        )
        in details.memberships
    )
    assert disabled is not None
    assert disabled.disabled is True
    assert stats.disabled_users == 1
    assert (
        await repo.update_user(uuid7(), PlatformAdminUserUpdate(disabled=True)) is None
    )
    assert await repo.get_user_details(uuid7()) is None


@pytest.mark.asyncio
async def test_update_organization_limits_changes_only_given_limits(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    repo = PlatformAdminRepository(data.engine)

    updated = await repo.update_organization_limits(
        data.organization.id, OrganizationLimitsUpdate(orbits_limit=7)
    )

    assert updated is not None
    assert updated.limits.orbits_limit == 7
    assert updated.limits.members_limit == TEST_ORGANIZATION_LIMITS["members_limit"]
    assert [(member.user_id, member.role) for member in updated.members] == [
        (data.user.id, OrgRole.OWNER)
    ]
    assert (
        await repo.update_organization_limits(
            uuid7(), OrganizationLimitsUpdate(orbits_limit=7)
        )
        is None
    )


@pytest.mark.asyncio
async def test_raised_user_organizations_limit_is_enforced(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    data = create_organization_with_user
    admin_repo = PlatformAdminRepository(data.engine)
    user_repo = UserRepository(data.engine)
    memberships = await user_repo.get_user_organizations_membership_count(data.user.id)

    lowered = await admin_repo.update_user(
        data.user.id, PlatformAdminUserUpdate(organizations_limit=memberships)
    )
    with pytest.raises(OrganizationLimitReachedError):
        await user_repo.create_organization(
            data.user.id, OrganizationCreateIn(name="blocked")
        )
    await admin_repo.update_user(
        data.user.id, PlatformAdminUserUpdate(organizations_limit=memberships + 1)
    )
    created = await user_repo.create_organization(
        data.user.id, OrganizationCreateIn(name="allowed")
    )

    assert lowered is not None
    assert lowered.organizations_limit == memberships
    assert created.name == "allowed"
    assert await user_repo.get_user_organizations_limit(data.user.id) == (
        memberships + 1
    )


@pytest.mark.asyncio
async def test_new_users_get_default_organizations_limit(
    create_organization_with_user: OrganizationFixtureData,
) -> None:
    repo = UserRepository(create_organization_with_user.engine)

    assert (
        await repo.get_user_organizations_limit(create_organization_with_user.user.id)
        == 5
    )
    assert await repo.get_user_organizations_limit(uuid7()) is None
