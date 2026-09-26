import datetime
from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid7

import pytest
from luml.handlers.orbits import OrbitHandler
from luml.infra.exceptions import (
    NotFoundError,
    OrbitMemberNotFoundError,
    OrbitNotFoundError,
)
from luml.models import OrganizationMemberOrm
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
from luml.schemas.organization import OrgRole
from luml.schemas.user import UserOut

handler = OrbitHandler()

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
OTHER_ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
OWNER_ORGANIZATION_ID = UUID("0199c337-0aa1-7c33-8f6c-2c6d0a4e91be")
OWNER_ORBIT_ID = UUID("0199c337-0aa2-7b45-9d21-4f8e3c7a15d0")
OWNER_BUCKET_SECRET_ID = UUID("0199c337-0aa3-7e57-b8f0-9a1c6d2e4f83")


def _scoped_bucket_secret(
    stored: Mock,
) -> Callable[..., Coroutine[Any, Any, Mock | None]]:
    """Mirror BucketSecretRepository.get_bucket_secret organization scoping."""

    async def scoped_get(
        secret_id: UUID, organization_id: UUID | None = None
    ) -> Mock | None:
        if secret_id != stored.id:
            return None
        if organization_id is not None and stored.organization_id != organization_id:
            return None
        return stored

    return scoped_get


def _owner_orbits() -> dict[UUID, Orbit]:
    return {
        OWNER_ORBIT_ID: Orbit(
            id=OWNER_ORBIT_ID,
            name="owner-orbit",
            organization_id=OWNER_ORGANIZATION_ID,
            bucket_secret_id=OWNER_BUCKET_SECRET_ID,
            total_members=1,
            role=None,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
    }


@pytest.fixture
def test_orbit() -> Orbit:
    return Orbit(
        id=uuid7(),
        name="test",
        organization_id=uuid7(),
        bucket_secret_id=uuid7(),
        total_members=1,
        role=None,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest.fixture
def test_orbit_member() -> OrbitMember:
    return OrbitMember(
        id=uuid7(),
        orbit_id=uuid7(),
        role=OrbitRole.MEMBER,
        user=UserOut(
            id=uuid7(),
            email=f"email_{uuid7()}@example.org",
            full_name="Kathy Hall",
            disabled=False,
            photo=None,
        ),
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@pytest.fixture
def test_orbit_details(test_orbit_member: OrbitMember) -> OrbitDetails:
    return OrbitDetails(
        id=uuid7(),
        name="test",
        organization_id=uuid7(),
        bucket_secret_id=uuid7(),
        members=[test_orbit_member],
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_organization_orbits_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.create_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit(
    mock_get_bucket_secret: AsyncMock,
    mock_create_orbit: AsyncMock,
    mock_get_organization_orbits_count: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_orbit: Orbit,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    mocked_orbit = test_orbit

    mock_get_bucket_secret.return_value = Mock(
        id=mocked_orbit.id,
        organization_id=mocked_orbit.organization_id,
        name="test_secret",
    )
    orbit_to_create = OrbitCreateIn(
        name=mocked_orbit.name,
        bucket_secret_id=mocked_orbit.bucket_secret_id,
    )

    mock_create_orbit.return_value = mocked_orbit
    mock_get_organization_orbits_count.return_value = 0
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_organization_details.return_value = Mock(orbits_limit=10, total_orbits=0)

    result = await handler.create_organization_orbit(
        user_id, mocked_orbit.organization_id, orbit_to_create
    )

    assert result == mocked_orbit

    mock_get_bucket_secret.assert_awaited_once_with(
        mocked_orbit.bucket_secret_id, mocked_orbit.organization_id
    )
    mock_create_orbit.assert_awaited_once_with(
        mocked_orbit.organization_id, orbit_to_create
    )


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.create_orbit",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit_makes_org_admin_creator_orbit_admin(
    mock_get_bucket_secret: AsyncMock,
    mock_create_orbit: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_orbit: Orbit,
) -> None:
    mock_get_bucket_secret.return_value = Mock(
        id=test_orbit.bucket_secret_id,
        organization_id=test_orbit.organization_id,
    )
    mock_create_orbit.return_value = test_orbit
    mock_get_organization_member_role.return_value = OrgRole.ADMIN
    mock_get_organization_details.return_value = Mock(orbits_limit=10, total_orbits=0)
    orbit_to_create = OrbitCreateIn(
        name=test_orbit.name, bucket_secret_id=test_orbit.bucket_secret_id
    )

    result = await handler.create_organization_orbit(
        USER_ID, test_orbit.organization_id, orbit_to_create
    )

    created = mock_create_orbit.await_args.args[1]
    assert created.members == [
        OrbitMemberCreateSimple(user_id=USER_ID, role=OrbitRole.ADMIN)
    ]
    assert result.permissions is not None
    assert "delete" in result.permissions["orbit"]


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_organization_orbits_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.create_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit_secret_not_found(
    mock_create_orbit: AsyncMock,
    mock_get_orbits_count: AsyncMock,
    mock_get_secret: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_org_role: AsyncMock,
    test_orbit: Orbit,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    orbit = test_orbit

    orbit_to_create = OrbitCreateIn(
        name=orbit.name,
        bucket_secret_id=orbit.bucket_secret_id,
    )

    mock_get_orbits_count.return_value = 0
    mock_get_secret.return_value = None
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_organization_details.return_value = Mock(orbits_limit=10, total_orbits=0)

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.create_organization_orbit(
            user_id, orbit.organization_id, orbit_to_create
        )

    assert error.value.status_code == 404
    mock_create_orbit.assert_not_called()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.UserRepository.get_organization_details",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_organization_orbits_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.create_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_organization_orbit_secret_wrong_org(
    mock_create_orbit: AsyncMock,
    mock_get_orbits_count: AsyncMock,
    mock_get_secret: AsyncMock,
    mock_get_organization_details: AsyncMock,
    mock_get_org_role: AsyncMock,
    test_orbit: Orbit,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    orbit = test_orbit
    orbit_to_create = OrbitCreateIn(
        name=orbit.name,
        bucket_secret_id=orbit.bucket_secret_id,
    )

    mock_get_orbits_count.return_value = 0
    mock_get_secret.side_effect = _scoped_bucket_secret(
        Mock(id=orbit.bucket_secret_id, organization_id=organization_id)
    )
    mock_get_org_role.return_value = OrgRole.OWNER
    mock_get_organization_details.return_value = Mock(orbits_limit=10, total_orbits=0)

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.create_organization_orbit(
            user_id, orbit.organization_id, orbit_to_create
        )

    assert error.value.status_code == 404
    mock_create_orbit.assert_not_called()


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_organization_orbits",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_orbits(
    mock_get_organization_orbits: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_orbit: Orbit,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    orbit = test_orbit
    expected = [orbit]

    mock_get_organization_orbits.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    result = await handler.get_organization_orbits(user_id, orbit.organization_id)

    assert result == expected

    mock_get_organization_orbits.assert_awaited_once_with(
        orbit.organization_id, user_id
    )


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_organization_orbits",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_organization_orbits_adds_orbit_role_permissions_for_org_admin(
    mock_get_organization_orbits: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    test_orbit: Orbit,
) -> None:
    own_orbit = test_orbit.model_copy(update={"id": uuid7(), "role": OrbitRole.ADMIN})
    other_orbit = test_orbit.model_copy(update={"id": uuid7(), "role": None})
    mock_get_organization_orbits.return_value = [own_orbit, other_orbit]
    mock_get_organization_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_organization_orbits(USER_ID, test_orbit.organization_id)

    permissions = {orbit.id: orbit.permissions for orbit in result}
    assert "delete" in permissions[own_orbit.id]["orbit"]
    assert "delete" not in permissions[other_orbit.id]["orbit"]


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit(
    mock_get_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit_details: OrbitDetails,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    expected = test_orbit_details

    mock_get_orbit.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_orbit(user_id, expected.organization_id, expected.id)

    assert result == expected
    mock_get_orbit.assert_awaited_once_with(expected.id, expected.organization_id)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_not_found(
    mock_get_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_get_orbit.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
        await handler.get_orbit(user_id, organization_id, orbit_id)

    assert error.value.status_code == 404
    mock_get_orbit.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit(
    mock_update_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit_details: OrbitDetails,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")

    expected = test_orbit_details

    mock_update_orbit.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    update_orbit = OrbitUpdate(name="new_name")
    result = await handler.update_orbit(
        user_id, expected.organization_id, expected.id, update_orbit
    )

    assert result == expected
    mock_update_orbit.assert_awaited_once_with(
        expected.id, expected.organization_id, update_orbit
    )


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_not_found(
    mock_update_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    update_orbit = OrbitUpdate(name="new_name")

    mock_update_orbit.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
        await handler.update_orbit(user_id, organization_id, orbit_id, update_orbit)

    assert error.value.status_code == 404
    mock_update_orbit.assert_awaited_once_with(orbit_id, organization_id, update_orbit)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.delete_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit(
    mock_delete_orbit: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_delete_orbit.return_value = True
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    await handler.delete_orbit(user_id, organization_id, orbit_id)
    mock_delete_orbit.assert_awaited_once_with(orbit_id, organization_id)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.delete_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_not_found(
    mock_delete_orbit: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    """A missing orbit must fail exactly like a foreign one: 404, same message."""
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    mock_delete_orbit.return_value = False
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
        await handler.delete_orbit(USER_ID, OTHER_ORGANIZATION_ID, orbit_id)

    assert error.value.status_code == 404


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_members",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_get_orbit_members(
    mock_get_orbit_members: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit_member: OrbitMember,
) -> None:
    UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    expected = [test_orbit_member]

    mock_get_orbit_members.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.get_orbit_members(
        expected[0].user.id, organization_id, expected[0].orbit_id
    )

    assert result == expected
    mock_get_orbit_members.assert_awaited_once_with(expected[0].orbit_id)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.emails.EmailHandler.send_added_to_orbit_email",
    new_callable=MagicMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_members_count",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.create_orbit_member",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.UserRepository.get_organization_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_create_orbit_member(
    mock_get_organization_member: AsyncMock,
    mock_create_orbit_member: AsyncMock,
    mock_get_orbit_members_count: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_send_added_to_orbit_email: MagicMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit_member: OrbitMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    expected = test_orbit_member

    create_member = OrbitMemberCreate(
        user_id=user_id,
        orbit_id=expected.orbit_id,
        role=expected.role,
    )

    mock_get_organization_member.return_value = OrganizationMemberOrm(
        id=uuid7(),
        user_id=uuid7(),
        organization_id=organization_id,
        role=OrgRole.OWNER,
    )
    mock_create_orbit_member.return_value = expected
    mock_get_orbit_members_count.return_value = 0
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN
    mock_get_orbit_simple.return_value = Mock(
        bucket_secret_id=1, organization_id=organization_id, name="name"
    )

    result = await handler.create_orbit_member(
        expected.user.id, organization_id, create_member
    )

    assert result == expected
    mock_create_orbit_member.assert_awaited_once_with(create_member)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit_member",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member(
    mock_get_orbit_member: AsyncMock,
    mock_update_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit_member: OrbitMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    initial_member = test_orbit_member
    expected = initial_member.model_copy()
    expected.role = OrbitRole.ADMIN

    update_member = UpdateOrbitMember(id=expected.id, role=OrbitRole.ADMIN)

    mock_get_orbit_member.return_value = initial_member
    mock_update_orbit_member.return_value = expected
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    result = await handler.update_orbit_member(
        user_id, organization_id, expected.orbit_id, update_member
    )

    assert result == expected
    mock_update_orbit_member.assert_awaited_once_with(update_member)


@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit_member",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_member_not_found(
    mock_get_orbit_member: AsyncMock,
    mock_update_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
    orbit_id = UUID("0199c337-09f3-753e-9def-b27745e69be6")

    update_member = UpdateOrbitMember(id=uuid7(), role=OrbitRole.ADMIN)

    mock_get_orbit_member.return_value = None
    mock_update_orbit_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    with pytest.raises(
        OrbitMemberNotFoundError, match="Orbit member not found"
    ) as error:
        await handler.update_orbit_member(
            user_id, organization_id, orbit_id, update_member
        )

    assert error.value.status_code == 404


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.delete_orbit_member",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_member",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_member(
    mock_get_orbit_member: AsyncMock,
    mock_delete_orbit_member: AsyncMock,
    mock_get_orbit_member_role: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit_member: OrbitMember,
) -> None:
    user_id = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
    organization_id = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")

    member = test_orbit_member

    mock_get_orbit_member.return_value = member
    mock_delete_orbit_member.return_value = None
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_orbit_member_role.return_value = OrgRole.ADMIN

    await handler.delete_orbit_member(
        user_id, organization_id, member.orbit_id, member.id
    )
    mock_delete_orbit_member.assert_awaited_once_with(member.id)


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_from_another_organization(
    mock_update_orbit: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    stored = _owner_orbits()

    async def scoped_update(
        orbit_id: UUID, organization_id: UUID, update: OrbitUpdate
    ) -> Orbit | None:
        orbit = stored.get(orbit_id)
        if not orbit or orbit.organization_id != organization_id:
            return None
        stored[orbit_id] = orbit.model_copy(
            update=update.model_dump(exclude_unset=True)
        )
        return stored[orbit_id]

    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_update_orbit.side_effect = scoped_update

    with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
        await handler.update_orbit(
            USER_ID,
            OTHER_ORGANIZATION_ID,
            OWNER_ORBIT_ID,
            OrbitUpdate(name="renamed"),
        )

    assert error.value.status_code == 404
    assert stored[OWNER_ORBIT_ID].name == "owner-orbit"


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.delete_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_delete_orbit_from_another_organization(
    mock_delete_orbit: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
) -> None:
    stored = _owner_orbits()

    async def scoped_delete(orbit_id: UUID, organization_id: UUID) -> bool:
        orbit = stored.get(orbit_id)
        if not orbit or orbit.organization_id != organization_id:
            return False
        del stored[orbit_id]
        return True

    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_delete_orbit.side_effect = scoped_delete

    with pytest.raises(OrbitNotFoundError, match="Orbit not found") as error:
        await handler.delete_orbit(USER_ID, OTHER_ORGANIZATION_ID, OWNER_ORBIT_ID)

    assert error.value.status_code == 404
    assert OWNER_ORBIT_ID in stored


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_with_foreign_bucket_secret(
    mock_update_orbit: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit: Orbit,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_bucket_secret.side_effect = _scoped_bucket_secret(
        Mock(id=OWNER_BUCKET_SECRET_ID, organization_id=OWNER_ORGANIZATION_ID)
    )

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.update_orbit(
            USER_ID,
            test_orbit.organization_id,
            test_orbit.id,
            OrbitUpdate(bucket_secret_id=OWNER_BUCKET_SECRET_ID),
        )

    assert error.value.status_code == 404
    mock_update_orbit.assert_not_called()


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_with_nonexistent_bucket_secret(
    mock_update_orbit: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit: Orbit,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_bucket_secret.return_value = None

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.update_orbit(
            USER_ID,
            test_orbit.organization_id,
            test_orbit.id,
            OrbitUpdate(bucket_secret_id=uuid7()),
        )

    assert error.value.status_code == 404
    mock_update_orbit.assert_not_called()


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_with_null_bucket_secret(
    mock_update_orbit: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit: Orbit,
) -> None:
    """An explicit null is present in the payload, so it is validated and rejected."""
    mock_get_organization_member_role.return_value = OrgRole.OWNER

    with pytest.raises(NotFoundError, match="Bucket secret not found") as error:
        await handler.update_orbit(
            USER_ID,
            test_orbit.organization_id,
            test_orbit.id,
            OrbitUpdate(bucket_secret_id=None),
        )

    assert error.value.status_code == 404
    mock_get_bucket_secret.assert_not_called()
    mock_update_orbit.assert_not_called()


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_without_bucket_secret_skips_validation(
    mock_update_orbit: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit: Orbit,
) -> None:
    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_update_orbit.return_value = test_orbit

    update_orbit = OrbitUpdate(name="new_name")
    result = await handler.update_orbit(
        USER_ID,
        test_orbit.organization_id,
        test_orbit.id,
        update_orbit,
    )

    assert result == test_orbit
    mock_get_bucket_secret.assert_not_called()
    mock_update_orbit.assert_awaited_once_with(
        test_orbit.id, test_orbit.organization_id, update_orbit
    )
    assert "bucket_secret_id" not in update_orbit.model_fields_set


@patch(
    "luml.handlers.orbits.OrbitRepository.get_orbit_simple",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.permissions.UserRepository.get_organization_member_role",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.BucketSecretRepository.get_bucket_secret",
    new_callable=AsyncMock,
)
@patch(
    "luml.handlers.orbits.OrbitRepository.update_orbit",
    new_callable=AsyncMock,
)
@pytest.mark.asyncio
async def test_update_orbit_with_own_bucket_secret(
    mock_update_orbit: AsyncMock,
    mock_get_bucket_secret: AsyncMock,
    mock_get_organization_member_role: AsyncMock,
    mock_get_orbit_simple: AsyncMock,
    test_orbit: Orbit,
) -> None:
    new_secret_id = uuid7()
    updated = test_orbit.model_copy(update={"bucket_secret_id": new_secret_id})

    mock_get_organization_member_role.return_value = OrgRole.OWNER
    mock_get_bucket_secret.return_value = Mock(
        id=new_secret_id, organization_id=test_orbit.organization_id
    )
    mock_update_orbit.return_value = updated

    update_orbit = OrbitUpdate(bucket_secret_id=new_secret_id)
    result = await handler.update_orbit(
        USER_ID, test_orbit.organization_id, test_orbit.id, update_orbit
    )

    assert result.bucket_secret_id == new_secret_id
    mock_get_bucket_secret.assert_awaited_once_with(
        new_secret_id, test_orbit.organization_id
    )
    mock_update_orbit.assert_awaited_once_with(
        test_orbit.id, test_orbit.organization_id, update_orbit
    )
