from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid7

import pytest
from fastapi.testclient import TestClient
from luml.infra.exceptions import ApplicationError
from luml.schemas.artifacts import (
    Artifact,
    ArtifactCreateIn,
    ArtifactDeleteDeployment,
    ArtifactDeleteFailure,
    ArtifactDeleteReason,
    ArtifactDeleteTrack,
    ArtifactDeleteURL,
    ArtifactsDeleteResponse,
    ArtifactsDeleteURLsResponse,
    ArtifactStatus,
    ArtifactType,
    CreateArtifactResponse,
    LumlArtifactManifest,
)
from luml.schemas.deployment import DeploymentStatus
from luml.schemas.general import SortOrder
from luml.schemas.storage import S3UploadDetails

from tests.support.auth import API_KEY_USER, SIGNED_IN_USER
from tests.support.ids import (
    ARTIFACT_ID,
    COLLECTION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    USER_ID,
)

ARTIFACTS_PATH = (
    f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}"
    f"/collections/{COLLECTION_ID}/artifacts"
)
ORBIT_ARTIFACTS_PATH = (
    f"/v1/organizations/{ORGANIZATION_ID}/orbits/{ORBIT_ID}/artifacts"
)


class TestOrbitArtifacts:
    @pytest.mark.parametrize(
        ("principal", "scope"),
        [(SIGNED_IN_USER, "jwt"), (API_KEY_USER, "api_key")],
        ids=["jwt", "api_key"],
        indirect=["principal"],
    )
    @patch(
        "luml.handlers.artifacts.ArtifactHandler.create_artifact",
        new_callable=AsyncMock,
    )
    def test_create_artifact_route_forwards_inputs_and_auth_scopes(
        self,
        mock_create_artifact: AsyncMock,
        scope: str,
        client: TestClient,
    ) -> None:
        manifest = LumlArtifactManifest(
            artifact_type="model",
            variant="pipeline",
            producer_name="test",
            producer_version="1.0",
            producer_tags=[],
            payload={},
        )
        artifact = ArtifactCreateIn(
            file_name="model.luml",
            name="model",
            extra_values={},
            manifest=manifest,
            file_hash="hash",
            file_index={},
            size=1,
            lineage_inputs=[ARTIFACT_ID],
        )
        expected = CreateArtifactResponse(
            artifact=Artifact(
                id=ARTIFACT_ID,
                collection_id=COLLECTION_ID,
                file_name="model.luml",
                name="model",
                extra_values={},
                manifest=manifest,
                file_hash="hash",
                file_index={},
                bucket_location="orbit/collection/model.luml",
                size=1,
                unique_identifier="uid",
                status=ArtifactStatus.PENDING_UPLOAD,
                created_at=datetime(2026, 1, 1),
                type=ArtifactType.MODEL,
            ),
            upload_details=S3UploadDetails(
                url="https://bucket/upload",
                bucket_location="orbit/collection/model.luml",
                bucket_secret_id=uuid7(),
            ),
        )
        mock_create_artifact.return_value = expected

        response = client.post(
            ARTIFACTS_PATH, json=artifact.model_dump(mode="json", by_alias=True)
        )

        assert response.status_code == 200
        assert response.json() == expected.model_dump(mode="json", by_alias=True)
        mock_create_artifact.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            COLLECTION_ID,
            artifact,
            ["authenticated", scope],
        )

    @patch(
        "luml.handlers.artifacts.ArtifactHandler.request_delete_urls",
        new_callable=AsyncMock,
    )
    def test_request_delete_urls_collapses_duplicates_and_shapes_response(
        self, mock_request_delete_urls: AsyncMock, client: TestClient
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

        response = client.post(
            f"{ARTIFACTS_PATH}/delete-urls",
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
        self,
        mock_request_delete_urls: AsyncMock,
        artifact_ids: list[str],
        client: TestClient,
    ) -> None:
        response = client.post(
            f"{ARTIFACTS_PATH}/delete-urls",
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
        self, mock_confirm_deletions: AsyncMock, force: bool, client: TestClient
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

        response = client.request("DELETE", ARTIFACTS_PATH, json=body)

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
        self,
        mock_confirm_deletions: AsyncMock,
        artifact_ids: list[str],
        client: TestClient,
    ) -> None:
        response = client.request(
            "DELETE",
            ARTIFACTS_PATH,
            json={"artifact_ids": artifact_ids},
        )

        assert response.status_code == 422
        mock_confirm_deletions.assert_not_awaited()

    @patch(
        "luml.handlers.artifacts.ArtifactHandler.get_collection_artifacts",
        new_callable=AsyncMock,
    )
    def test_list_forwards_cursor_and_maps_invalid_cursor_to_400(
        self, mock_get_artifacts: AsyncMock, client: TestClient
    ) -> None:
        mock_get_artifacts.side_effect = ApplicationError("Invalid cursor")

        response = client.get(ORBIT_ARTIFACTS_PATH, params={"cursor": "garbage"})

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid cursor"}
        mock_get_artifacts.assert_awaited_once_with(
            user_id=USER_ID,
            organization_id=ORGANIZATION_ID,
            orbit_id=ORBIT_ID,
            artifact_types=None,
            cursor_str="garbage",
            limit=50,
            sort_by="created_at",
            order=SortOrder.DESC,
            collection_ids=None,
            search=None,
            excluded_tracks=None,
        )
