from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx2 import ASGITransport, AsyncClient
from luml.handlers.organizations import OrganizationHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser, OrganizationOrm
from luml.repositories.invites import InviteRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import (
    CreateOrganizationInvite,
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.user import CreateUser
from luml.service import AppService
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.authentication import AuthCredentials

from tests.support.seeds import OrganizationFixtureData


@pytest.fixture
async def authentication(
    seeded_organization: OrganizationFixtureData, monkeypatch: pytest.MonkeyPatch
) -> AsyncMock:
    data = seeded_organization
    authentication = AsyncMock(
        return_value=(
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=data.user.id, email=data.user.email),
        )
    )
    monkeypatch.setattr(JWTAuthenticationBackend, "authenticate", authentication)
    return authentication


@pytest.fixture
async def client(
    seeded_organization: OrganizationFixtureData,
    authentication: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient]:
    data = seeded_organization
    repository = UserRepository(data.engine)
    monkeypatch.setattr(
        OrganizationHandler, "_OrganizationHandler__user_repository", repository
    )
    monkeypatch.setattr(
        OrganizationHandler,
        "_OrganizationHandler__invites_repository",
        InviteRepository(data.engine),
    )
    monkeypatch.setattr(
        OrganizationHandler, "_OrganizationHandler__email_handler", AsyncMock()
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__user_repository", repository
    )
    async with AsyncClient(
        transport=ASGITransport(app=AppService()), base_url="http://test"
    ) as test_client:
        yield test_client


class TestOrganizationInviteEmail:
    @pytest.mark.parametrize("legacy", [False, True])
    @pytest.mark.parametrize("action", ["accept", "reject"])
    async def test_mixed_case_invite_can_be_listed_and_resolved(
        self,
        client: AsyncClient,
        authentication: AsyncMock,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
        legacy: bool,
        action: str,
    ) -> None:
        data = seeded_organization
        users = UserRepository(data.engine)
        invites = InviteRepository(data.engine)
        invitee = await users.create_user(
            new_user.model_copy(update={"email": "john_x@example.com"})
        )
        if legacy:
            created = await invites.create_organization_invite(
                CreateOrganizationInvite(
                    email="John_x@Example.com",
                    role=OrgRole.MEMBER,
                    organization_id=data.organization.id,
                    invited_by=data.user.id,
                )
            )
            invite_id = str(created.id)
        else:
            response = await client.post(
                f"/v1/organizations/{data.organization.id}/invitations",
                json={"email": "John_x@Example.com", "role": "member"},
            )
            assert response.status_code == 200
            assert response.json()["email"] == "john_x@example.com"
            invite_id = response.json()["id"]

        duplicate = await client.post(
            f"/v1/organizations/{data.organization.id}/invitations",
            json={"email": "JOHN_X@example.com", "role": "member"},
        )
        assert duplicate.status_code == 409

        authentication.return_value = (
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=invitee.id, email=invitee.email),
        )
        listed = await client.get("/v1/users/me/invitations")
        assert listed.status_code == 200
        assert [invite["id"] for invite in listed.json()] == [invite_id]

        resolved = await client.post(f"/v1/users/me/invitations/{invite_id}/{action}")
        assert resolved.status_code == (200 if action == "accept" else 204)
        assert await invites.get_invites_by_user_email(invitee.email) == []
        membership = await users.get_organization_member(
            data.organization.id, invitee.id
        )
        if action == "accept":
            assert membership is not None
            assert membership.role == OrgRole.MEMBER
        else:
            assert membership is None

    @pytest.mark.parametrize("action", ["accept", "reject"])
    async def test_other_email_cannot_list_or_resolve_invite(
        self,
        client: AsyncClient,
        seeded_organization: OrganizationFixtureData,
        action: str,
    ) -> None:
        data = seeded_organization
        invites = InviteRepository(data.engine)
        created = await invites.create_organization_invite(
            CreateOrganizationInvite(
                email="Other@Example.com",
                role=OrgRole.MEMBER,
                organization_id=data.organization.id,
                invited_by=data.user.id,
            )
        )

        listed = await client.get("/v1/users/me/invitations")
        assert listed.status_code == 200
        assert listed.json() == []
        response = await client.post(f"/v1/users/me/invitations/{created.id}/{action}")
        assert response.status_code == 403
        assert response.json() == {"detail": "This invite is not for you"}
        assert await invites.get_invite(created.id) is not None

    async def test_mixed_case_self_invite_is_rejected(
        self, client: AsyncClient, seeded_organization: OrganizationFixtureData
    ) -> None:
        data = seeded_organization
        response = await client.post(
            f"/v1/organizations/{data.organization.id}/invitations",
            json={"email": data.user.email.upper(), "role": "member"},
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "You can't invite yourself"}
        assert (
            await InviteRepository(data.engine).get_invites_by_organization_id(
                data.organization.id
            )
            == []
        )

    async def test_mixed_case_member_invite_is_rejected(
        self,
        client: AsyncClient,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        data = seeded_organization
        users = UserRepository(data.engine)
        member = await users.create_user(
            new_user.model_copy(update={"email": "member@example.com"})
        )
        await users.create_organization_member(
            OrganizationMemberCreate(
                organization_id=data.organization.id,
                user_id=member.id,
                role=OrgRole.MEMBER,
            )
        )
        response = await client.post(
            f"/v1/organizations/{data.organization.id}/invitations",
            json={"email": "Member@Example.com", "role": "member"},
        )

        assert response.status_code == 409
        assert (
            await InviteRepository(data.engine).get_invites_by_organization_id(
                data.organization.id
            )
            == []
        )


class TestOrganizationInviteLimits:
    async def test_pending_invites_use_slots_and_cancellation_frees_one(
        self, client: AsyncClient, seeded_organization: OrganizationFixtureData
    ) -> None:
        data = seeded_organization
        async with AsyncSession(data.engine) as session:
            await session.execute(
                update(OrganizationOrm)
                .where(OrganizationOrm.id == data.organization.id)
                .values(members_limit=3)
            )
            await session.commit()

        path = f"/v1/organizations/{data.organization.id}/invitations"
        first = await client.post(
            path, json={"email": "first@example.com", "role": "member"}
        )
        second = await client.post(
            path, json={"email": "second@example.com", "role": "member"}
        )
        assert first.status_code == second.status_code == 200

        refused = await client.post(
            path, json={"email": "third@example.com", "role": "member"}
        )
        assert refused.status_code == 409
        assert refused.json() == {
            "detail": "The organization has no free member slots. "
            "Cancel pending invites or upgrade to invite more people."
        }
        assert len((await client.get(path)).json()) == 2

        canceled = await client.delete(f"{path}/{first.json()['id']}")
        assert canceled.status_code == 204
        retried = await client.post(
            path, json={"email": "third@example.com", "role": "member"}
        )
        assert retried.status_code == 200
        assert len((await client.get(path)).json()) == 2

    async def test_legacy_invites_stay_valid_but_acceptance_checks_members(
        self,
        client: AsyncClient,
        authentication: AsyncMock,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        data = seeded_organization
        users = UserRepository(data.engine)
        invites = InviteRepository(data.engine)
        invitees = [
            await users.create_user(
                new_user.model_copy(update={"email": f"legacy-{index}@example.com"})
            )
            for index in range(3)
        ]
        pending = [
            await invites.create_organization_invite(
                CreateOrganizationInvite(
                    email=user.email,
                    role=OrgRole.MEMBER,
                    organization_id=data.organization.id,
                    invited_by=data.user.id,
                )
            )
            for user in invitees
        ]
        async with AsyncSession(data.engine) as session:
            await session.execute(
                update(OrganizationOrm)
                .where(OrganizationOrm.id == data.organization.id)
                .values(members_limit=2)
            )
            await session.commit()

        refused = await client.post(
            f"/v1/organizations/{data.organization.id}/invitations",
            json={"email": "new@example.com", "role": "member"},
        )
        assert refused.status_code == 409
        assert (
            len(await invites.get_invites_by_organization_id(data.organization.id)) == 3
        )

        for index, status in [(0, 200), (1, 409)]:
            user = invitees[index]
            authentication.return_value = (
                AuthCredentials(["authenticated", "jwt"]),
                AuthUser(user_id=user.id, email=user.email),
            )
            response = await client.post(
                f"/v1/users/me/invitations/{pending[index].id}/accept"
            )
            assert response.status_code == status
            if status == 409:
                assert response.json() == {
                    "detail": "Organization reached maximum number of users"
                }

        assert await users.get_organization_members_count(data.organization.id) == 2
        remaining = await invites.get_invites_by_organization_id(data.organization.id)
        assert {invite.id for invite in remaining} == {
            invite.id for invite in pending[1:]
        }
