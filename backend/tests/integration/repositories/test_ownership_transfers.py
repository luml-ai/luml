import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid7

import pytest
from luml.infra.exceptions import ApplicationError, InsufficientPermissionsError
from luml.models import OrganizationOrm, OwnershipTransferOrm
from luml.repositories.ownership_transfers import OwnershipTransferRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import OrgRole, UpdateOrganizationMember
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.seeds import OrganizationWithMembersFixtureData


@pytest.mark.parametrize("role", [OrgRole.MEMBER, OrgRole.ADMIN])
async def test_request_accept_and_once_only_notice(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
    role: OrgRole,
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    users = UserRepository(data.engine)
    recipient = data.members[1]
    await users.update_organization_member(
        data.organization.id, recipient.id, UpdateOrganizationMember(role=role)
    )
    request = await repo.create(data.organization.id, data.user.id, recipient.id)
    assert request.recipient_email == recipient.user.email
    assert timedelta(days=7) == request.expires_at - request.created_at
    assert (
        await users.get_organization_member_role(data.organization.id, data.user.id)
        == OrgRole.OWNER
    )
    assert [item.id for item in await repo.list_received(recipient.user.id)] == [
        request.id
    ]
    await repo.resolve(data.organization.id, request.id, recipient.user.id, "accepted")
    assert (
        await users.get_organization_member_role(data.organization.id, data.user.id)
        == OrgRole.ADMIN
    )
    assert (
        await users.get_organization_member_role(
            data.organization.id, recipient.user.id
        )
        == OrgRole.OWNER
    )
    notices = await repo.consume_notices(data.organization.id, data.user.id)
    assert [notice.status for notice in notices] == ["accepted"]
    assert await repo.consume_notices(data.organization.id, data.user.id) == []


@pytest.mark.parametrize("action", ["declined", "cancelled"])
async def test_closing_request_keeps_roles_and_rejects_replay(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
    action: Literal["accepted", "declined", "cancelled"],
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    recipient = data.members[1]
    request = await repo.create(data.organization.id, data.user.id, recipient.id)
    actor = data.user.id if action == "cancelled" else recipient.user.id
    await repo.resolve(data.organization.id, request.id, actor, action)
    assert (
        await UserRepository(data.engine).get_organization_member_role(
            data.organization.id, data.user.id
        )
        == OrgRole.OWNER
    )
    for closed_action in ("accepted", "declined", "cancelled"):
        closed_actor = (
            data.user.id if closed_action == "cancelled" else recipient.user.id
        )
        with pytest.raises(ApplicationError, match="no longer pending"):
            await repo.resolve(
                data.organization.id, request.id, closed_actor, closed_action
            )
    notices = await repo.consume_notices(data.organization.id, data.user.id)
    assert [notice.status for notice in notices] == (
        ["declined"] if action == "declined" else []
    )
    assert await repo.consume_notices(data.organization.id, data.user.id) == []
    assert await repo.pending(data.organization.id, data.user.id) is None
    await repo.create(data.organization.id, data.user.id, data.members[2].id)


async def test_request_validation_and_authorization(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    with pytest.raises(InsufficientPermissionsError):
        await repo.create(
            data.organization.id, data.members[1].user.id, data.members[2].id
        )
    with pytest.raises(ApplicationError):
        await repo.create(data.organization.id, data.user.id, data.member.id)
    with pytest.raises(ApplicationError):
        await repo.create(data.organization.id, data.user.id, uuid7())
    request = await repo.create(data.organization.id, data.user.id, data.members[1].id)
    with pytest.raises(ApplicationError, match="cancel"):
        await repo.create(data.organization.id, data.user.id, data.members[2].id)
    for action in ["accepted", "declined", "cancelled"]:
        with pytest.raises(InsufficientPermissionsError):
            await repo.resolve(
                data.organization.id, request.id, data.members[2].user.id, action
            )
    with pytest.raises(InsufficientPermissionsError):
        await repo.pending(data.organization.id, data.members[1].user.id)


@pytest.mark.parametrize("action", ["accepted", "declined", "cancelled"])
async def test_expiry_closes_request(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
    action: Literal["accepted", "declined", "cancelled"],
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    request = await repo.create(data.organization.id, data.user.id, data.members[1].id)
    async with AsyncSession(data.engine) as session, session.begin():
        await session.execute(
            update(OwnershipTransferOrm).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )
        )
    actor = data.user.id if action == "cancelled" else data.members[1].user.id
    with pytest.raises(ApplicationError, match="no longer pending"):
        await repo.resolve(data.organization.id, request.id, actor, action)
    assert await repo.list_received(data.members[1].user.id) == []
    await repo.create(data.organization.id, data.user.id, data.members[2].id)


@pytest.mark.parametrize(
    "removal", ["remove", "leave", "account", "organization", "owner_account"]
)
async def test_deletion_closes_request(
    seeded_organization_with_members: OrganizationWithMembersFixtureData, removal: str
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    users = UserRepository(data.engine)
    recipient = data.members[1]
    request = await repo.create(data.organization.id, data.user.id, recipient.id)
    if removal == "remove":
        await users.delete_organization_member(data.organization.id, recipient.id)
    elif removal == "leave":
        await users.delete_organization_member_by_user_id(
            recipient.user.id, data.organization.id
        )
    elif removal == "account":
        await users.delete_user(recipient.user.email)
    elif removal == "owner_account":
        await users.delete_user(data.user.email)
    else:
        async with AsyncSession(data.engine) as session, session.begin():
            await session.execute(
                delete(OrganizationOrm).where(
                    OrganizationOrm.id == data.organization.id
                )
            )
    assert await repo.list_received(recipient.user.id) == []
    with pytest.raises(ApplicationError, match="no longer pending"):
        await repo.resolve(
            data.organization.id, request.id, recipient.user.id, "accepted"
        )


async def test_role_change_keeps_request_valid_and_stale_sender_closes_it(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    users = UserRepository(data.engine)
    recipient = data.members[1]
    request = await repo.create(data.organization.id, data.user.id, recipient.id)
    await users.update_organization_member(
        data.organization.id, recipient.id, UpdateOrganizationMember(role=OrgRole.ADMIN)
    )
    assert (await repo.list_received(recipient.user.id))[0].id == request.id
    async with AsyncSession(data.engine) as session, session.begin():
        from luml.models import OrganizationMemberOrm

        await session.execute(
            update(OrganizationMemberOrm)
            .where(OrganizationMemberOrm.id == data.member.id)
            .values(role=OrgRole.ADMIN)
        )
    with pytest.raises(ApplicationError, match="no longer pending"):
        await repo.resolve(
            data.organization.id, request.id, recipient.user.id, "accepted"
        )
    async with AsyncSession(data.engine) as session:
        assert (
            await session.scalar(
                select(OwnershipTransferOrm.status).where(
                    OwnershipTransferOrm.id == request.id
                )
            )
            == "cancelled"
        )


async def test_accept_cancel_race_has_one_winner(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    recipient = data.members[1]
    request = await repo.create(data.organization.id, data.user.id, recipient.id)
    results = await asyncio.gather(
        repo.resolve(data.organization.id, request.id, recipient.user.id, "accepted"),
        repo.resolve(data.organization.id, request.id, data.user.id, "cancelled"),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ApplicationError) for result in results) == 1
    outcome = next(
        result for result in results if not isinstance(result, BaseException)
    )
    assert outcome.status in {"accepted", "cancelled"}
    role = await UserRepository(data.engine).get_organization_member_role(
        data.organization.id, recipient.user.id
    )
    assert role == (OrgRole.OWNER if outcome.status == "accepted" else OrgRole.MEMBER)


async def test_recipient_can_receive_requests_from_multiple_organizations(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    from luml.schemas.organization import OrganizationCreateIn, OrganizationMemberCreate

    data = seeded_organization_with_members
    users = UserRepository(data.engine)
    repo = OwnershipTransferRepository(data.engine)
    recipient = data.members[1]
    other = await users.create_organization(
        data.user.id, OrganizationCreateIn(name="Other organization")
    )
    other_membership = await users.create_organization_member(
        OrganizationMemberCreate(
            user_id=recipient.user.id, organization_id=other.id, role=OrgRole.MEMBER
        )
    )
    first = await repo.create(data.organization.id, data.user.id, recipient.id)
    second = await repo.create(other.id, data.user.id, other_membership.id)
    assert {item.id for item in await repo.list_received(recipient.user.id)} == {
        first.id,
        second.id,
    }
    with pytest.raises(ApplicationError, match="no longer pending"):
        await repo.resolve(other.id, first.id, recipient.user.id, "accepted")


async def test_pending_request_preserves_organization_deletion_guard(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    from luml.infra.exceptions import OrganizationDeleteError

    data = seeded_organization_with_members
    users = UserRepository(data.engine)
    repo = OwnershipTransferRepository(data.engine)
    await repo.create(data.organization.id, data.user.id, data.members[1].id)
    with pytest.raises(OrganizationDeleteError):
        await users.delete_organization(data.organization.id)
    for member in data.members[1:]:
        await users.delete_organization_member(data.organization.id, member.id)
    assert await users.delete_organization(data.organization.id)


async def test_concurrent_requests_have_one_winner(
    seeded_organization_with_members: OrganizationWithMembersFixtureData,
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    results = await asyncio.gather(
        repo.create(data.organization.id, data.user.id, data.members[1].id),
        repo.create(data.organization.id, data.user.id, data.members[2].id),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ApplicationError) for result in results) == 1


@pytest.mark.parametrize("account", [False, True])
async def test_decline_notice_survives_recipient_departure(
    seeded_organization_with_members: OrganizationWithMembersFixtureData, account: bool
) -> None:
    data = seeded_organization_with_members
    repo = OwnershipTransferRepository(data.engine)
    users = UserRepository(data.engine)
    recipient = data.members[1]
    request = await repo.create(data.organization.id, data.user.id, recipient.id)
    await repo.resolve(data.organization.id, request.id, recipient.user.id, "declined")
    if account:
        await users.delete_user(recipient.user.email)
    else:
        await users.delete_organization_member(data.organization.id, recipient.id)
    notices = await repo.consume_notices(data.organization.id, data.user.id)
    assert [notice.recipient_email for notice in notices] == [recipient.user.email]
