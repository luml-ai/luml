import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.organizations import OrganizationHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.users import UserRepository
from luml.schemas.organization import (
    OrganizationCreateIn,
    OrganizationMemberCreate,
    OrgRole,
)
from luml.schemas.user import CreateUser
from luml.service import AppService
from starlette.authentication import AuthCredentials

from tests.support.seeds import OrganizationFixtureData


@pytest.fixture
async def client(
    seeded_organization: OrganizationFixtureData,
    monkeypatch: pytest.MonkeyPatch,
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
        JWTAuthenticationBackend,
        "authenticate",
        AsyncMock(
            return_value=(
                AuthCredentials(["authenticated", "jwt"]),
                AuthUser(user_id=data.user.id, email=data.user.email),
            )
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=AppService()), base_url="http://test"
    ) as test_client:
        yield test_client


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
