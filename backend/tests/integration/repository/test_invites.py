import uuid

import pytest

from dataforce_studio.models import OrganizationOrm
from dataforce_studio.repositories.invites import InviteRepository
from dataforce_studio.schemas.organization import CreateOrganizationInvite, OrgRole
from dataforce_studio.schemas.user import User


def get_invite_obj(
    organization: OrganizationOrm, user: User
) -> CreateOrganizationInvite:
    return CreateOrganizationInvite(
        email=f"invite_{uuid.uuid4()}@gmail.com",
        role=OrgRole.MEMBER,
        organization_id=organization.id,
        invited_by=user.id,
    )


@pytest.mark.asyncio
async def test_create_organization_invite(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    invite = get_invite_obj(organization, user)

    created_invite = await repo.create_organization_invite(invite)

    assert created_invite.email == invite.email
    assert created_invite.organization_id == invite.organization_id


@pytest.mark.asyncio
async def test_delete_organization_invite(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    invite = get_invite_obj(organization, user)

    created_invite = await repo.create_organization_invite(invite)

    deleted_invite = await repo.delete_organization_invite(created_invite.id)

    assert deleted_invite is None


@pytest.mark.asyncio
async def test_get_invite(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    created_invite = await repo.create_organization_invite(
        get_invite_obj(organization, user)
    )
    fetched_invite = await repo.get_invite(created_invite.id)

    assert fetched_invite.id == created_invite.id
    assert fetched_invite.email == created_invite.email
    assert fetched_invite.invited_by_user.id == user.id
    assert fetched_invite.organization_id == created_invite.organization_id


@pytest.mark.asyncio
async def test_get_invite_where(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    for _ in range(4):
        await repo.create_organization_invite(get_invite_obj(organization, user))

    invites = await repo.get_invites_by_organization_id(organization.id)

    assert isinstance(invites, list)
    assert len(invites) == 4
    assert invites[0].organization_id == organization.id


@pytest.mark.asyncio
async def test_delete_invite_where(create_organization_with_user: dict) -> None:
    data = create_organization_with_user
    engine, user, organization = data["engine"], data["user"], data["organization"]
    repo = InviteRepository(engine)

    for _ in range(4):
        await repo.create_organization_invite(get_invite_obj(organization, user))

    deleted_invites = await repo.delete_all_organization_invites(organization.id)

    invites = await repo.get_invites_by_organization_id(organization.id)

    assert deleted_invites is None
    assert len(invites) == 0
