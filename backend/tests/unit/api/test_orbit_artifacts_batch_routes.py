from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid7

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luml.api.orbits.orbit_artifacts import artifacts_router
from luml.models import AuthUser
from luml.schemas.artifacts import (
    ArtifactDeleteDeployment,
    ArtifactDeleteFailure,
    ArtifactDeleteReason,
    ArtifactDeleteTrack,
    ArtifactDeleteURL,
    ArtifactsDeleteResponse,
    ArtifactsDeleteURLsResponse,
)
from luml.schemas.deployment import DeploymentStatus
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.middleware.authentication import AuthenticationMiddleware

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
COLLECTION_ID = UUID("0199c337-09f4-7a01-9f5f-5f68db62cf70")


def _create_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(artifacts_router, prefix="/v1/organizations")
    authentication = Mock(spec=AuthenticationBackend)
    authentication.authenticate = AsyncMock(
        return_value=(
            AuthCredentials(["authenticated", "jwt"]),
            AuthUser(user_id=USER_ID, email="test@example.com"),
        )
    )
    app.add_middleware(AuthenticationMiddleware, backend=authentication)
    return TestClient(app)


def _artifacts_url() -> str:
    return (
        f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}"
        f"/collections/{COLLECTION_ID}/artifacts"
    )


class TestOrbitArtifactsBatchRoutes:
    @patch(
        "luml.handlers.artifacts.ArtifactHandler.request_delete_urls",
        new_callable=AsyncMock,
    )
    def test_request_delete_urls_collapses_duplicates_and_shapes_response(
        self, mock_request_delete_urls: AsyncMock
    ) -> None:
        artifact_id = uuid7()
        blocked_id = uuid7()
        deployment = ArtifactDeleteDeployment(
            id=uuid7(), name="deployment", status=DeploymentStatus.FAILED
        )
        mock_request_delete_urls.return_value = ArtifactsDeleteURLsResponse(
            urls=[
                ArtifactDeleteURL(
                    artifact_id=artifact_id,
                    name="artifact",
                    url="https://bucket/delete",
                )
            ],
            failed=[
                ArtifactDeleteFailure(
                    artifact_id=blocked_id,
                    name="blocked",
                    reason=ArtifactDeleteReason.DEPLOYMENTS,
                    deployments=[deployment],
                )
            ],
        )

        response = _create_test_client().post(
            f"{_artifacts_url()}/delete-urls",
            json={
                "artifact_ids": [
                    str(artifact_id),
                    str(artifact_id),
                    str(blocked_id),
                ]
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "urls": [
                {
                    "artifact_id": str(artifact_id),
                    "name": "artifact",
                    "url": "https://bucket/delete",
                }
            ],
            "failed": [
                {
                    "artifact_id": str(blocked_id),
                    "name": "blocked",
                    "reason": "deployments",
                    "deployments": [
                        {
                            "id": str(deployment.id),
                            "name": "deployment",
                            "status": "failed",
                        }
                    ],
                    "tracks": [],
                }
            ],
        }
        mock_request_delete_urls.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [artifact_id, blocked_id],
        )

    @pytest.mark.parametrize(
        "artifact_ids",
        [[], [str(uuid7()) for _ in range(101)]],
        ids=["empty", "too-many"],
    )
    @patch(
        "luml.handlers.artifacts.ArtifactHandler.request_delete_urls",
        new_callable=AsyncMock,
    )
    def test_request_delete_urls_validates_body(
        self, mock_request_delete_urls: AsyncMock, artifact_ids: list[str]
    ) -> None:
        response = _create_test_client().post(
            f"{_artifacts_url()}/delete-urls",
            json={"artifact_ids": artifact_ids},
        )

        assert response.status_code == 422
        mock_request_delete_urls.assert_not_awaited()

    @pytest.mark.parametrize("force", [False, True])
    @patch(
        "luml.handlers.artifacts.ArtifactHandler.confirm_deletions",
        new_callable=AsyncMock,
    )
    def test_confirm_passes_force_and_shapes_response(
        self, mock_confirm_deletions: AsyncMock, force: bool
    ) -> None:
        deleted_id = uuid7()
        tracked_id = uuid7()
        track = ArtifactDeleteTrack(id=uuid7(), name="release")
        mock_confirm_deletions.return_value = ArtifactsDeleteResponse(
            deleted=[deleted_id],
            failed=[
                ArtifactDeleteFailure(
                    artifact_id=tracked_id,
                    name="tracked",
                    reason=ArtifactDeleteReason.TRACKS,
                    tracks=[track],
                )
            ],
        )
        body: dict[str, object] = {"artifact_ids": [str(deleted_id), str(tracked_id)]}
        if force:
            body["force"] = True

        response = _create_test_client().request("DELETE", _artifacts_url(), json=body)

        assert response.status_code == 200
        assert response.json() == {
            "deleted": [str(deleted_id)],
            "failed": [
                {
                    "artifact_id": str(tracked_id),
                    "name": "tracked",
                    "reason": "tracks",
                    "deployments": [],
                    "tracks": [{"id": str(track.id), "name": "release"}],
                }
            ],
        }
        mock_confirm_deletions.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            [deleted_id, tracked_id],
            force=force,
        )

    @pytest.mark.parametrize(
        "artifact_ids",
        [[], [str(uuid7()) for _ in range(101)]],
        ids=["empty", "too-many"],
    )
    @patch(
        "luml.handlers.artifacts.ArtifactHandler.confirm_deletions",
        new_callable=AsyncMock,
    )
    def test_confirm_validates_body(
        self, mock_confirm_deletions: AsyncMock, artifact_ids: list[str]
    ) -> None:
        response = _create_test_client().request(
            "DELETE",
            _artifacts_url(),
            json={"artifact_ids": artifact_ids},
        )

        assert response.status_code == 422
        mock_confirm_deletions.assert_not_awaited()
