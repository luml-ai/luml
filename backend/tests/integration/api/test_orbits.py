from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.orbits import OrbitHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.orbit import OrbitMemberCreate, OrbitRole
from luml.schemas.organization import OrganizationMemberCreate, OrgRole
from luml.schemas.user import CreateUser, User
from luml.service import AppService
from starlette.authentication import AuthCredentials

from tests.support.builders import create_sibling_organization
from tests.support.seeds import OrbitWithMembersFixtureData


@pytest.fixture
async def caller(
    request: pytest.FixtureRequest,
    seeded_orbit_with_members: OrbitWithMembersFixtureData,
    new_user: CreateUser,
) -> User:
    data = seeded_orbit_with_members
    role = getattr(request, "param", OrgRole.MEMBER)
    if role == OrgRole.OWNER:
        return data.user

    repository = UserRepository(data.engine)
    user = await repository.create_user(
        new_user.model_copy(update={"email": f"caller-{uuid7()}@example.com"})
    )
    await repository.create_organization_member(
        OrganizationMemberCreate(
            organization_id=data.organization.id, user_id=user.id, role=role
        )
    )
    return user


@pytest.fixture
async def client(
    caller: User,
    seeded_orbit_with_members: OrbitWithMembersFixtureData,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient]:
    data = seeded_orbit_with_members
    user_repository = UserRepository(data.engine)
    orbit_repository = OrbitRepository(data.engine)
    monkeypatch.setattr(OrbitHandler, "_OrbitHandler__user_repository", user_repository)
    monkeypatch.setattr(
        OrbitHandler, "_OrbitHandler__orbits_repository", orbit_repository
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__user_repository", user_repository
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__orbits_repository", orbit_repository
    )
    monkeypatch.setattr(
        JWTAuthenticationBackend,
        "authenticate",
        AsyncMock(
            return_value=(
                AuthCredentials(["authenticated", "jwt"]),
                AuthUser(user_id=caller.id, email=caller.email),
            )
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=AppService()), base_url="http://test"
    ) as test_client:
        yield test_client


class TestOrbitReadPermissions:
    @pytest.mark.parametrize(
        ("caller", "orbit_role", "expected_status"),
        [
            (OrgRole.MEMBER, None, 403),
            (OrgRole.MEMBER, OrbitRole.MEMBER, 200),
            (OrgRole.MEMBER, OrbitRole.ADMIN, 200),
            (OrgRole.ADMIN, None, 200),
            (OrgRole.OWNER, None, 200),
        ],
        indirect=["caller"],
    )
    async def test_list_and_detail_respect_orbit_access(
        self,
        client: AsyncClient,
        caller: User,
        seeded_orbit_with_members: OrbitWithMembersFixtureData,
        orbit_role: OrbitRole | None,
        expected_status: int,
    ) -> None:
        data = seeded_orbit_with_members
        if orbit_role:
            await OrbitRepository(data.engine).create_orbit_member(
                OrbitMemberCreate(
                    user_id=caller.id, orbit_id=data.orbit.id, role=orbit_role
                )
            )
        path = f"/v1/organizations/{data.organization.id}/orbits"

        listed = await client.get(path)
        detail = await client.get(f"{path}/{data.orbit.id}")

        assert listed.status_code == 200
        assert detail.status_code == expected_status
        if expected_status == 403:
            assert listed.json() == []
            assert detail.json() == {"detail": "Not enough rights"}
        else:
            assert [orbit["id"] for orbit in listed.json()] == [str(data.orbit.id)]
            body = detail.json()
            assert body["id"] == str(data.orbit.id)
            assert body["bucket_secret_id"] == str(data.bucket_secret.id)
            assert data.members[0].user.email in {
                member["user"]["email"] for member in body["members"]
            }

    async def test_removed_orbit_member_loses_list_and_detail_access(
        self,
        client: AsyncClient,
        caller: User,
        seeded_orbit_with_members: OrbitWithMembersFixtureData,
    ) -> None:
        data = seeded_orbit_with_members
        repository = OrbitRepository(data.engine)
        member = await repository.create_orbit_member(
            OrbitMemberCreate(
                user_id=caller.id, orbit_id=data.orbit.id, role=OrbitRole.MEMBER
            )
        )
        path = f"/v1/organizations/{data.organization.id}/orbits"
        assert (await client.get(f"{path}/{data.orbit.id}")).status_code == 200

        await repository.delete_orbit_member(member.id, data.orbit.id)

        listed = await client.get(path)
        detail = await client.get(f"{path}/{data.orbit.id}")
        assert listed.status_code == 200
        assert listed.json() == []
        assert detail.status_code == 403
        assert detail.json() == {"detail": "Not enough rights"}

    @pytest.mark.parametrize("missing_orbit", [False, True])
    async def test_foreign_or_missing_orbit_returns_not_found(
        self,
        client: AsyncClient,
        caller: User,
        seeded_orbit_with_members: OrbitWithMembersFixtureData,
        missing_orbit: bool,
    ) -> None:
        data = seeded_orbit_with_members
        organization = await create_sibling_organization(data.engine, caller.id)
        orbit_id = uuid7() if missing_orbit else data.orbit.id

        response = await client.get(
            f"/v1/organizations/{organization.id}/orbits/{orbit_id}"
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Orbit not found"}
