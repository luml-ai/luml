from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import uuid7

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.orbits import OrbitHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.bucket_secrets import S3BucketSecretCreate
from luml.schemas.orbit import OrbitMember, OrbitMemberCreate, OrbitRole
from luml.schemas.organization import OrganizationMemberCreate, OrgRole
from luml.service import AppService
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.authentication import AuthCredentials

from tests.support.builders import create_sibling_orbit, create_sibling_organization
from tests.support.seeds import OrbitWithMembersFixtureData


@pytest.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch,
    engine: AsyncEngine,
    seeded_orbit_with_members: OrbitWithMembersFixtureData,
) -> AsyncGenerator[AsyncClient]:
    data = seeded_orbit_with_members
    caller = data.members[0].user
    user_repository = UserRepository(engine)
    orbit_repository = OrbitRepository(engine)
    await user_repository.create_organization_member(
        OrganizationMemberCreate(
            organization_id=data.organization.id,
            user_id=caller.id,
            role=OrgRole.MEMBER,
        )
    )
    monkeypatch.setattr(
        OrbitHandler, "_OrbitHandler__orbits_repository", orbit_repository
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__orbits_repository", orbit_repository
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__user_repository", user_repository
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


@pytest.fixture
async def foreign_member(
    request: pytest.FixtureRequest,
    seeded_orbit_with_members: OrbitWithMembersFixtureData,
) -> OrbitMember:
    data = seeded_orbit_with_members
    organization_id = data.organization.id
    bucket_secret_id = data.bucket_secret.id
    if getattr(request, "param", True):
        other_organization = await create_sibling_organization(
            data.engine, data.user.id
        )
        organization_id = other_organization.id
        secret = await BucketSecretRepository(data.engine).create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=organization_id,
                endpoint="s3",
                bucket_name="other-bucket",
                region="us-east-1",
            )
        )
        bucket_secret_id = secret.id

    other_orbit = await create_sibling_orbit(
        data.engine, organization_id, bucket_secret_id
    )
    return await OrbitRepository(data.engine).create_orbit_member(
        OrbitMemberCreate(
            user_id=data.members[1].user.id,
            orbit_id=other_orbit.id,
            role=OrbitRole.MEMBER,
        )
    )


class TestOrbitMemberMutations:
    @pytest.mark.parametrize(
        "foreign_member", [False, True], indirect=True, ids=["same-org", "other-org"]
    )
    @pytest.mark.parametrize("method", ["patch", "delete"])
    @pytest.mark.parametrize("missing_path_id", [False, True])
    async def test_foreign_or_missing_path_member_returns_404_and_keeps_membership(
        self,
        client: AsyncClient,
        seeded_orbit_with_members: OrbitWithMembersFixtureData,
        foreign_member: OrbitMember,
        method: str,
        missing_path_id: bool,
    ) -> None:
        data = seeded_orbit_with_members
        path_id = uuid7() if missing_path_id else foreign_member.id
        response = await client.request(
            method,
            f"/v1/organizations/{data.organization.id}"
            f"/orbits/{data.orbit.id}/members/{path_id}",
            json={"id": str(foreign_member.id), "role": "admin"}
            if method == "patch"
            else None,
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Orbit member not found"}
        unchanged = await OrbitRepository(data.engine).get_orbit_member(
            foreign_member.id, foreign_member.orbit_id
        )
        assert unchanged is not None
        assert unchanged.role == OrbitRole.MEMBER

    async def test_local_path_member_can_be_updated_and_deleted_with_foreign_body_id(
        self,
        client: AsyncClient,
        seeded_orbit_with_members: OrbitWithMembersFixtureData,
        foreign_member: OrbitMember,
    ) -> None:
        data = seeded_orbit_with_members
        local_member = data.members[1]
        path = (
            f"/v1/organizations/{data.organization.id}"
            f"/orbits/{data.orbit.id}/members/{local_member.id}"
        )
        response = await client.patch(
            path, json={"id": str(foreign_member.id), "role": "admin"}
        )

        assert response.status_code == 200
        assert response.json()["id"] == str(local_member.id)
        assert response.json()["orbit_id"] == str(data.orbit.id)
        assert response.json()["role"] == "admin"
        repository = OrbitRepository(data.engine)
        updated = await repository.get_orbit_member(local_member.id, data.orbit.id)
        assert updated is not None
        assert updated.role == OrbitRole.ADMIN

        response = await client.delete(path)

        assert response.status_code == 204
        assert await repository.get_orbit_member(local_member.id, data.orbit.id) is None
        unchanged = await repository.get_orbit_member(
            foreign_member.id, foreign_member.orbit_id
        )
        assert unchanged is not None
        assert unchanged.role == OrbitRole.MEMBER
