import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.organizations import OrganizationHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser, UserOrm
from luml.repositories.invites import InviteRepository
from luml.repositories.users import UserRepository
from luml.schemas.organization import (
    OrganizationCreateIn,
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
def authentication(seeded_organization: OrganizationFixtureData) -> AsyncMock:
    user = seeded_organization.user
    return AsyncMock(
        return_value=(
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=user.id, email=user.email),
        )
    )


@pytest.fixture
async def client(
    seeded_organization: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
    authentication: AsyncMock,
) -> AsyncGenerator[AsyncClient]:
    data = seeded_organization
    repository = UserRepository(data.engine)
    monkeypatch.setattr(
        OrganizationHandler, "_OrganizationHandler__user_repository", repository
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__user_repository", repository
    )
    monkeypatch.setattr(
        OrganizationHandler,
        "_OrganizationHandler__invites_repository",
        InviteRepository(data.engine),
    )
    monkeypatch.setattr(
        OrganizationHandler, "_OrganizationHandler__email_handler", Mock()
    )
    monkeypatch.setattr(
        JWTAuthenticationBackend,
        "authenticate",
        authentication,
    )
    async with AsyncClient(
        transport=ASGITransport(app=AppService()), base_url="http://test"
    ) as test_client:
        yield test_client


class TestOrganizationMembershipConsent:
    async def test_direct_enrollment_cannot_exhaust_another_users_quota(
        self,
        client: AsyncClient,
        authentication: AsyncMock,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
    ) -> None:
        data = seeded_organization
        repository = UserRepository(data.engine)
        victim = await repository.create_user(
            new_user.model_copy(update={"email": f"victim-{uuid.uuid4()}@example.com"})
        )
        async with AsyncSession(data.engine) as session:
            await session.execute(
                update(UserOrm)
                .where(UserOrm.id == victim.id)
                .values(organizations_limit=2)
            )
            await session.commit()

        response = await client.post(
            f"/v1/organizations/{data.organization.id}/members",
            json={"user_id": str(victim.id), "role": "member"},
        )

        assert response.status_code == 405
        assert (
            await repository.get_organization_member(data.organization.id, victim.id)
            is None
        )

        authentication.return_value = (
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=victim.id, email=victim.email),
        )
        organizations = await client.get("/v1/users/me/organizations")
        assert organizations.status_code == 200
        assert len(organizations.json()) == 1

        created = await client.post(
            "/v1/organizations", json={"name": "my own organization"}
        )
        assert created.status_code == 200
        assert created.json()["name"] == "my own organization"

    @pytest.mark.parametrize("accept", [True, False])
    async def test_only_invitee_can_consent_to_membership(
        self,
        client: AsyncClient,
        authentication: AsyncMock,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
        accept: bool,
    ) -> None:
        data = seeded_organization
        repository = UserRepository(data.engine)
        invitee = await repository.create_user(
            new_user.model_copy(update={"email": f"invitee-{uuid.uuid4()}@example.com"})
        )
        invitation = await client.post(
            f"/v1/organizations/{data.organization.id}/invitations",
            json={"email": invitee.email, "role": "member"},
        )
        assert invitation.status_code == 200
        invite_id = invitation.json()["id"]
        assert (
            await repository.get_organization_member(data.organization.id, invitee.id)
            is None
        )
        assert await repository.get_user_organizations_membership_count(invitee.id) == 1

        unauthorized = await client.post(f"/v1/users/me/invitations/{invite_id}/accept")
        assert unauthorized.status_code == 403
        assert (
            await repository.get_organization_member(data.organization.id, invitee.id)
            is None
        )

        authentication.return_value = (
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=invitee.id, email=invitee.email),
        )
        action = "accept" if accept else "reject"
        response = await client.post(f"/v1/users/me/invitations/{invite_id}/{action}")

        member = await repository.get_organization_member(
            data.organization.id, invitee.id
        )
        if accept:
            assert response.status_code == 200
            assert member is not None
            assert member.role == OrgRole.MEMBER
            assert (
                await repository.get_user_organizations_membership_count(invitee.id)
                == 2
            )
        else:
            assert response.status_code == 204
            assert member is None
            assert (
                await repository.get_user_organizations_membership_count(invitee.id)
                == 1
            )
        assert (
            await InviteRepository(data.engine).get_invite(uuid.UUID(invite_id)) is None
        )


class TestOrganizationMemberScope:
    @pytest.mark.parametrize("method", ["PATCH", "DELETE"])
    @pytest.mark.parametrize("role", [OrgRole.MEMBER, OrgRole.ADMIN, OrgRole.OWNER])
    async def test_foreign_member_returns_404_without_mutating_membership(
        self,
        client: AsyncClient,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
        method: str,
        role: OrgRole,
    ) -> None:
        data = seeded_organization
        repository = UserRepository(data.engine)
        owner = await repository.create_user(
            new_user.model_copy(update={"email": f"owner-{uuid.uuid4()}@example.com"})
        )
        foreign_org = await repository.create_organization(
            owner.id, OrganizationCreateIn(name="foreign organization")
        )
        if role == OrgRole.OWNER:
            target_user = owner
            owner_member = await repository.get_organization_member(
                foreign_org.id, owner.id
            )
            assert owner_member is not None
            target = owner_member.to_organization_member()
        else:
            target_user = await repository.create_user(
                new_user.model_copy(
                    update={"email": f"target-{uuid.uuid4()}@example.com"}
                )
            )
            target = await repository.create_organization_member(
                OrganizationMemberCreate(
                    organization_id=foreign_org.id, user_id=target_user.id, role=role
                )
            )

        response = await client.request(
            method,
            f"/v1/organizations/{data.organization.id}/members/{target.id}",
            json={"role": "member"} if method == "PATCH" else None,
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Organization member not found"}
        unchanged = await repository.get_organization_member(
            foreign_org.id, target_user.id
        )
        assert unchanged is not None
        assert unchanged.id == target.id
        assert unchanged.role == role

    @pytest.mark.parametrize("method", ["PATCH", "DELETE"])
    async def test_missing_member_returns_404(
        self,
        client: AsyncClient,
        seeded_organization: OrganizationFixtureData,
        method: str,
    ) -> None:
        response = await client.request(
            method,
            f"/v1/organizations/{seeded_organization.organization.id}"
            f"/members/{uuid.uuid4()}",
            json={"role": "member"} if method == "PATCH" else None,
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Organization member not found"}

    @pytest.mark.parametrize("method", ["PATCH", "DELETE"])
    async def test_owner_can_mutate_admin_in_path_organization(
        self,
        client: AsyncClient,
        seeded_organization: OrganizationFixtureData,
        new_user: CreateUser,
        method: str,
    ) -> None:
        data = seeded_organization
        repository = UserRepository(data.engine)
        target_user = await repository.create_user(
            new_user.model_copy(update={"email": f"target-{uuid.uuid4()}@example.com"})
        )
        target = await repository.create_organization_member(
            OrganizationMemberCreate(
                organization_id=data.organization.id,
                user_id=target_user.id,
                role=OrgRole.ADMIN,
            )
        )

        response = await client.request(
            method,
            f"/v1/organizations/{data.organization.id}/members/{target.id}",
            json={"role": "member"} if method == "PATCH" else None,
        )

        persisted = await repository.get_organization_member(
            data.organization.id, target_user.id
        )
        if method == "PATCH":
            assert response.status_code == 200
            assert response.json()["id"] == str(target.id)
            assert response.json()["role"] == "member"
            assert persisted is not None
            assert persisted.role == OrgRole.MEMBER
        else:
            assert response.status_code == 204
            assert persisted is None
