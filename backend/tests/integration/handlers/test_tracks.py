import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
import pytest
from luml.handlers.permissions import PermissionsHandler
from luml.handlers.tracks import TracksHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.tracks import TrackEntryRepository, TrackRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import ArtifactCreate, ArtifactType
from luml.schemas.bucket_secrets import S3BucketSecretCreate
from luml.schemas.orbit import OrbitCreateIn, OrbitMemberCreate, OrbitRole
from luml.schemas.organization import OrganizationMemberCreate, OrgRole
from luml.schemas.tracks import TrackCreate, TrackEntryCreate
from luml.schemas.user import CreateUser
from luml.service import AppService
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.authentication import AuthCredentials

from tests.support.builders import (
    create_artifact,
    create_collection,
    create_sibling_orbit,
    create_sibling_organization,
)
from tests.support.seeds import OrbitFixtureData


@pytest.fixture
async def track_client(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    seeded_orbit: OrbitFixtureData,
    new_user: CreateUser,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[tuple[str, httpx.AsyncClient]]:
    method: str = request.param
    user_repository = UserRepository(engine)
    orbit_repository = OrbitRepository(engine)
    user = await user_repository.create_user(
        new_user.model_copy(update={"email": f"caller-{uuid.uuid4()}@example.com"})
    )
    await user_repository.create_organization_member(
        OrganizationMemberCreate(
            user_id=user.id,
            organization_id=seeded_orbit.organization.id,
            role=OrgRole.MEMBER,
        )
    )
    await orbit_repository.create_orbit_member(
        OrbitMemberCreate(
            user_id=user.id,
            orbit_id=seeded_orbit.orbit.id,
            role=OrbitRole.MEMBER if method == "PATCH" else OrbitRole.ADMIN,
        )
    )
    monkeypatch.setattr(
        JWTAuthenticationBackend,
        "authenticate",
        AsyncMock(
            return_value=(
                AuthCredentials(["authenticated", "jwt"]),
                AuthUser(user_id=user.id, email=user.email),
            )
        ),
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__user_repository", user_repository
    )
    monkeypatch.setattr(
        PermissionsHandler, "_PermissionsHandler__orbits_repository", orbit_repository
    )
    monkeypatch.setattr(
        TracksHandler, "_TracksHandler__orbit_repository", orbit_repository
    )
    monkeypatch.setattr(
        TracksHandler, "_TracksHandler__track_repository", TrackRepository(engine)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=AppService()), base_url="http://test"
    ) as client:
        yield method, client


@pytest.mark.parametrize("track_client", ["PATCH", "DELETE"], indirect=True)
@pytest.mark.parametrize("foreign_organization", [False, True])
async def test_track_mutations_reject_foreign_orbit_and_preserve_track(
    track_client: tuple[str, httpx.AsyncClient],
    seeded_orbit: OrbitFixtureData,
    new_artifact: ArtifactCreate,
    foreign_organization: bool,
) -> None:
    data = seeded_orbit
    if foreign_organization:
        organization = await create_sibling_organization(data.engine, data.user.id)
        secret = await BucketSecretRepository(data.engine).create_bucket_secret(
            S3BucketSecretCreate(
                organization_id=organization.id,
                endpoint="s3",
                bucket_name="foreign-bucket",
                region="us-east-1",
            )
        )
        victim_orbit = await OrbitRepository(data.engine).create_orbit(
            organization.id,
            OrbitCreateIn(name="foreign orbit", bucket_secret_id=secret.id),
        )
        assert victim_orbit is not None
    else:
        victim_orbit = await create_sibling_orbit(
            data.engine, data.organization.id, data.bucket_secret.id
        )
    repository = TrackRepository(data.engine)
    track = await repository.create_track(
        TrackCreate(
            orbit_id=victim_orbit.id, name="victim", artifact_type=ArtifactType.MODEL
        ),
        stage_names=["dev"],
    )
    collection = await create_collection(data.engine, victim_orbit.id, "victim")
    artifact = await create_artifact(
        data.engine, new_artifact, collection.id, name="victim artifact"
    )
    entry_repository = TrackEntryRepository(data.engine)
    entry = await entry_repository.create_entry(
        TrackEntryCreate(
            track_id=track.id,
            artifact_id=artifact.id,
            stage_id=track.stages[0].id,
            added_by=data.user.email,
        )
    )
    before = await repository.get_track(track.id)
    assert before is not None
    method, client = track_client
    body = (
        {"name": "pwned", "stages": [{"name": "replaced"}]}
        if method == "PATCH"
        else None
    )
    response = await client.request(
        method,
        f"/v1/organizations/{data.organization.id}/orbits/{data.orbit.id}/tracks/{track.id}",
        json=body,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Track not found"}
    after = await repository.get_track(track.id)
    assert after is not None
    assert after.name == "victim"
    assert after.stages == before.stages
    assert await entry_repository.get_entry(entry.id) == entry


@pytest.mark.parametrize("track_client", ["PATCH", "DELETE"], indirect=True)
async def test_track_mutations_reject_missing_track(
    track_client: tuple[str, httpx.AsyncClient],
    seeded_orbit: OrbitFixtureData,
) -> None:
    data = seeded_orbit
    method, client = track_client
    response = await client.request(
        method,
        f"/v1/organizations/{data.organization.id}/orbits/{data.orbit.id}/tracks/{uuid.uuid4()}",
        json={"name": "updated"} if method == "PATCH" else None,
    )
    assert response.status_code == 404


@pytest.mark.parametrize("track_client", ["PATCH", "DELETE"], indirect=True)
async def test_track_mutations_allow_own_orbit(
    track_client: tuple[str, httpx.AsyncClient],
    seeded_orbit: OrbitFixtureData,
) -> None:
    data = seeded_orbit
    repository = TrackRepository(data.engine)
    track = await repository.create_track(
        TrackCreate(
            orbit_id=data.orbit.id, name="own track", artifact_type=ArtifactType.MODEL
        ),
        stage_names=["dev"],
    )
    method, client = track_client
    response = await client.request(
        method,
        f"/v1/organizations/{data.organization.id}/orbits/{data.orbit.id}/tracks/{track.id}",
        json={"name": "updated", "stages": [{"name": "prod"}]}
        if method == "PATCH"
        else None,
    )
    after = await repository.get_track(track.id)
    if method == "PATCH":
        assert response.status_code == 200
        assert after is not None
        assert after.name == "updated"
        assert [stage.name for stage in after.stages] == ["prod"]
    else:
        assert response.status_code == 204
        assert after is None
