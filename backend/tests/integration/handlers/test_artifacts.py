import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from luml.handlers.artifacts import ArtifactHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.security import JWTAuthenticationBackend
from luml.models import AuthUser
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.lineage import LineageRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import (
    ArtifactCreate,
    ArtifactListed,
    ArtifactStatus,
    Manifest,
)
from luml.schemas.lineage import LineageVia
from luml.schemas.storage import S3UploadDetails
from luml.schemas.user import UpdateUser
from luml.service import AppService
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.authentication import AuthCredentials

from tests.support.builders import create_artifact
from tests.support.seeds import CollectionFixtureData


@pytest.fixture
def handler(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> ArtifactHandler:
    monkeypatch.setattr(
        ArtifactHandler, "_ArtifactHandler__repository", ArtifactRepository(engine)
    )
    monkeypatch.setattr(
        ArtifactHandler,
        "_ArtifactHandler__lineage_repository",
        LineageRepository(engine),
    )
    monkeypatch.setattr(
        ArtifactHandler, "_ArtifactHandler__user_repository", UserRepository(engine)
    )
    monkeypatch.setattr(
        ArtifactHandler, "_ArtifactHandler__orbit_repository", OrbitRepository(engine)
    )
    monkeypatch.setattr(
        ArtifactHandler,
        "_ArtifactHandler__collection_repository",
        CollectionRepository(engine),
    )
    return ArtifactHandler()


async def _get_listed_artifacts(
    engine: AsyncEngine,
    orbit_id: uuid.UUID,
    artifact_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ArtifactListed]:
    artifacts = await ArtifactRepository(engine).get_artifacts_by_ids_in_orbit(
        orbit_id, artifact_ids
    )
    return {artifact.id: artifact for artifact in artifacts}


class TestArtifactHandler:
    @pytest.mark.parametrize("full_name", ["Test User", None])
    @pytest.mark.parametrize(
        ("name_fields", "expected_name"),
        [
            ({"name": "Named Artifact"}, "Named Artifact"),
            ({}, "model.luml"),
            ({"name": None}, "model.luml"),
            ({"name": ""}, "model.luml"),
        ],
        ids=["named", "omitted-name", "null-name", "empty-name"],
    )
    async def test_create_artifact_route_persists_optional_name_fallbacks(
        self,
        handler: ArtifactHandler,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        monkeypatch: pytest.MonkeyPatch,
        manifest: Manifest,
        full_name: str | None,
        name_fields: dict[str, str | None],
        expected_name: str,
    ) -> None:
        data = seeded_collection
        await UserRepository(engine).update_user(
            UpdateUser(email=data.user.email, full_name=full_name)
        )
        monkeypatch.setattr(PermissionsHandler, "check_permissions", AsyncMock())
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
        upload_details = S3UploadDetails(
            url="https://storage.example/upload",
            bucket_location="upload/location",
            bucket_secret_id=data.bucket_secret.id,
        )
        monkeypatch.setattr(
            ArtifactHandler,
            "_get_storage_client",
            AsyncMock(
                return_value=AsyncMock(
                    create_upload=AsyncMock(return_value=upload_details)
                )
            ),
        )
        payload = {
            "file_name": "model.luml",
            "extra_values": {},
            "manifest": manifest.model_dump(mode="json"),
            "file_hash": "hash",
            "file_index": dict.fromkeys(
                [
                    "dtypes.json",
                    "env.json",
                    "manifest.json",
                    "meta.json",
                    "ops.json",
                    "variant_config.json",
                ],
                [0, 1],
            ),
            "size": 10,
            **name_fields,
        }
        async with AsyncClient(
            transport=ASGITransport(app=AppService(), raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/v1/organizations/{data.organization.id}/orbits/{data.orbit.id}"
                f"/collections/{data.collection.id}/artifacts",
                json=payload,
            )

        assert response.status_code == 200
        created = response.json()["artifact"]
        expected_creator = data.user.email if full_name is None else "Test User"
        assert created["name"] == expected_name
        assert created["created_by_user"] == expected_creator
        assert created["status"] == ArtifactStatus.PENDING_UPLOAD
        assert response.json()["upload_details"] == upload_details.model_dump(
            mode="json"
        )
        persisted = await ArtifactRepository(engine).get_artifact(
            uuid.UUID(created["id"])
        )
        assert persisted is not None
        assert persisted.name == expected_name
        assert persisted.created_by_user == expected_creator

    async def test_delete_artifact_removes_component_when_last_two_deleted_concurrently(
        self,
        handler: ArtifactHandler,
        engine: AsyncEngine,
        seeded_collection: CollectionFixtureData,
        new_artifact: ArtifactCreate,
    ) -> None:
        artifact_repository = ArtifactRepository(engine)
        lineage_repository = LineageRepository(engine)
        artifacts = [
            await create_artifact(
                engine,
                new_artifact,
                seeded_collection.collection.id,
                name=name,
                status=new_artifact.status,
            )
            for name in ["last-1", "last-2"]
        ]
        listed = await _get_listed_artifacts(
            engine, seeded_collection.orbit.id, [artifact.id for artifact in artifacts]
        )
        nodes = [
            await lineage_repository.get_or_create_node(
                seeded_collection.orbit.id, listed[artifact.id]
            )
            for artifact in artifacts
        ]
        await lineage_repository.create_edges(
            seeded_collection.orbit.id,
            [(nodes[0].id, nodes[1].id)],
            "Test User",
            LineageVia.API,
        )

        await asyncio.gather(
            handler._delete_artifact(seeded_collection.orbit.id, artifacts[0].id),
            handler._delete_artifact(seeded_collection.orbit.id, artifacts[1].id),
        )

        assert await artifact_repository.get_artifact(artifacts[0].id) is None
        assert await artifact_repository.get_artifact(artifacts[1].id) is None
        assert (
            await lineage_repository.get_nodes_by_ids(
                seeded_collection.orbit.id, [node.id for node in nodes]
            )
            == []
        )
