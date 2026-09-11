from unittest.mock import AsyncMock, Mock, call, patch

import httpx
import pytest

from luml_api import ArtifactBatchDeleteError, ArtifactDeleteError
from luml_api._exceptions import InternalServerError
from luml_api._types import ArtifactDeleteReason, ArtifactStatus
from luml_api.handlers.base_file_handler import BaseFileHandler
from luml_api.resources.artifacts import ArtifactResource, AsyncArtifactResource


def _url_entry(artifact_id: str, name: str | None = None) -> dict[str, str]:
    return {
        "artifact_id": artifact_id,
        "name": name or f"name-{artifact_id}",
        "url": f"https://storage.example.com/{artifact_id}",
    }


def _failure(
    artifact_id: str,
    reason: ArtifactDeleteReason,
    *,
    name: str | None = None,
    deployments: list[dict[str, str]] | None = None,
    tracks: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "name": name,
        "reason": reason,
        "deployments": deployments or [],
        "tracks": tracks or [],
    }


def _request_response(
    artifact_ids: list[str],
    *,
    failed: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "urls": [_url_entry(artifact_id) for artifact_id in artifact_ids],
        "failed": failed or [],
    }


def _confirmation_response(
    artifact_ids: list[str],
    *,
    failed: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {"deleted": artifact_ids, "failed": failed or []}


def _artifacts_path(client: Mock | AsyncMock) -> str:
    return (
        f"/v1/organizations/{client.organization}/orbits/{client.orbit}/"
        f"collections/{client.collection}/artifacts"
    )


def _server_error(method: str = "POST") -> InternalServerError:
    request = httpx.Request(method, "https://api.example.com/artifacts")
    response = httpx.Response(500, request=request, json={"detail": "failed"})
    return InternalServerError("failed", response=response, body=response.json())


class TestArtifactDeleteBatch:
    def test_runs_three_phases_with_exact_platform_calls(
        self, mock_sync_client: Mock
    ) -> None:
        artifact_ids = ["artifact-a", "artifact-b", "artifact-c"]
        mock_sync_client.post.return_value = _request_response(artifact_ids)
        mock_sync_client.delete.return_value = _confirmation_response(artifact_ids)
        resource = ArtifactResource(mock_sync_client)

        with patch.object(
            BaseFileHandler, "delete_file", return_value=True
        ) as bucket_delete:
            result = resource.delete_batch(artifact_ids)

        path = _artifacts_path(mock_sync_client)
        mock_sync_client.post.assert_called_once_with(
            f"{path}/delete-urls",
            json={"artifact_ids": artifact_ids},
        )
        bucket_delete.assert_has_calls(
            [
                call(f"https://storage.example.com/{artifact_id}")
                for artifact_id in artifact_ids
            ],
            any_order=True,
        )
        mock_sync_client.delete.assert_called_once_with(
            path,
            json={"artifact_ids": artifact_ids, "force": False},
        )
        assert result.deleted == artifact_ids
        assert result.failed == []

    def test_merges_failures_from_all_three_phases(
        self, mock_sync_client: Mock
    ) -> None:
        deployment = {"id": "deployment-b", "name": "api", "status": "failed"}
        track = {"id": "track-d", "name": "release"}
        phase_one_failure = _failure(
            "artifact-b",
            "deployments",
            name="B",
            deployments=[deployment],
        )
        phase_three_failure = _failure(
            "artifact-d",
            "tracks",
            name="D",
            tracks=[track],
        )
        mock_sync_client.post.return_value = _request_response(
            ["artifact-a", "artifact-c", "artifact-d"],
            failed=[phase_one_failure],
        )
        mock_sync_client.delete.return_value = _confirmation_response(
            ["artifact-a"],
            failed=[phase_three_failure],
        )
        resource = ArtifactResource(mock_sync_client)

        def delete_object(url: str) -> bool:
            return not url.endswith("artifact-c")

        with (
            patch.object(BaseFileHandler, "delete_file", side_effect=delete_object),
            patch.object(resource, "update") as update,
        ):
            result = resource.delete_batch(
                ["artifact-a", "artifact-b", "artifact-c", "artifact-d"]
            )

        assert result.deleted == ["artifact-a"]
        assert [failure.artifact_id for failure in result.failed] == [
            "artifact-b",
            "artifact-c",
            "artifact-d",
        ]
        assert [failure.reason for failure in result.failed] == [
            "deployments",
            "storage_error",
            "tracks",
        ]
        assert result.failed[0].deployments[0].status == "failed"
        assert result.failed[2].tracks[0].name == "release"
        update.assert_called_once_with(
            "artifact-c",
            status=ArtifactStatus.DELETION_FAILED,
            collection_id=mock_sync_client.collection,
        )
        mock_sync_client.delete.assert_called_once_with(
            _artifacts_path(mock_sync_client),
            json={
                "artifact_ids": ["artifact-a", "artifact-d"],
                "force": False,
            },
        )

    def test_bucket_404_is_confirmed(self, mock_sync_client: Mock) -> None:
        artifact_id = "artifact-a"
        mock_sync_client.post.return_value = _request_response([artifact_id])
        mock_sync_client.delete.return_value = _confirmation_response([artifact_id])
        resource = ArtifactResource(mock_sync_client)

        with patch(
            "luml_api.handlers.base_file_handler.httpx.delete",
            return_value=httpx.Response(404),
        ):
            result = resource.delete_batch([artifact_id])

        assert result.deleted == [artifact_id]
        mock_sync_client.delete.assert_called_once()

    def test_storage_failure_uses_url_name_and_updates_status(
        self, mock_sync_client: Mock
    ) -> None:
        artifact_id = "artifact-a"
        mock_sync_client.post.return_value = {
            "urls": [_url_entry(artifact_id, "Artifact A")],
            "failed": [],
        }
        resource = ArtifactResource(mock_sync_client)

        with (
            patch.object(BaseFileHandler, "delete_file", return_value=False),
            patch.object(resource, "update") as update,
        ):
            result = resource.delete_batch([artifact_id])

        assert result.deleted == []
        assert len(result.failed) == 1
        assert result.failed[0].artifact_id == artifact_id
        assert result.failed[0].name == "Artifact A"
        assert result.failed[0].reason == "storage_error"
        update.assert_called_once_with(
            artifact_id,
            status=ArtifactStatus.DELETION_FAILED,
            collection_id=mock_sync_client.collection,
        )
        mock_sync_client.delete.assert_not_called()

    def test_failed_status_update_does_not_raise(self, mock_sync_client: Mock) -> None:
        artifact_id = "artifact-a"
        mock_sync_client.post.return_value = _request_response([artifact_id])
        resource = ArtifactResource(mock_sync_client)

        with (
            patch.object(BaseFileHandler, "delete_file", return_value=False),
            patch.object(
                resource,
                "update",
                side_effect=RuntimeError("update failed"),
            ),
        ):
            result = resource.delete_batch([artifact_id])

        assert result.deleted == []
        assert [failure.reason for failure in result.failed] == ["storage_error"]
        mock_sync_client.delete.assert_not_called()

    def test_collapses_duplicates_before_chunking(self, mock_sync_client: Mock) -> None:
        distinct_ids = [f"artifact-{index}" for index in range(90)]
        artifact_ids = [*distinct_ids, *distinct_ids[:60]]
        mock_sync_client.post.return_value = _request_response(distinct_ids)
        mock_sync_client.delete.return_value = _confirmation_response(distinct_ids)
        resource = ArtifactResource(mock_sync_client)

        with patch.object(BaseFileHandler, "delete_file", return_value=True):
            result = resource.delete_batch(artifact_ids)

        mock_sync_client.post.assert_called_once_with(
            f"{_artifacts_path(mock_sync_client)}/delete-urls",
            json={"artifact_ids": distinct_ids},
        )
        assert result.deleted == distinct_ids
        assert len(set(result.deleted)) == 90

    def test_chunks_two_hundred_fifty_ids(self, mock_sync_client: Mock) -> None:
        artifact_ids = [f"artifact-{index}" for index in range(250)]
        chunks = [artifact_ids[:100], artifact_ids[100:200], artifact_ids[200:]]
        mock_sync_client.post.side_effect = [
            _request_response(chunk) for chunk in chunks
        ]
        mock_sync_client.delete.side_effect = [
            _confirmation_response(chunk) for chunk in chunks
        ]
        resource = ArtifactResource(mock_sync_client)

        with patch.object(BaseFileHandler, "delete_file", return_value=True):
            result = resource.delete_batch(artifact_ids)

        path = _artifacts_path(mock_sync_client)
        assert mock_sync_client.post.call_args_list == [
            call(f"{path}/delete-urls", json={"artifact_ids": chunk})
            for chunk in chunks
        ]
        assert mock_sync_client.delete.call_args_list == [
            call(path, json={"artifact_ids": chunk, "force": False}) for chunk in chunks
        ]
        assert result.deleted == artifact_ids

    def test_later_chunk_error_carries_partial_result(
        self, mock_sync_client: Mock
    ) -> None:
        artifact_ids = [f"artifact-{index}" for index in range(130)]
        first_chunk = artifact_ids[:100]
        remaining = artifact_ids[100:]
        cause = _server_error()
        mock_sync_client.post.side_effect = [
            _request_response(first_chunk),
            cause,
        ]
        mock_sync_client.delete.return_value = _confirmation_response(first_chunk)
        resource = ArtifactResource(mock_sync_client)

        with (
            patch.object(BaseFileHandler, "delete_file", return_value=True),
            pytest.raises(ArtifactBatchDeleteError) as error_info,
        ):
            resource.delete_batch(artifact_ids)

        error = error_info.value
        assert error.cause is cause
        assert error.__cause__ is cause
        assert error.deleted == first_chunk
        assert error.failed == []
        assert error.not_completed == remaining

    def test_confirmation_error_keeps_classified_failures(
        self, mock_sync_client: Mock
    ) -> None:
        deployment = {"id": "deployment-b", "name": "api", "status": "active"}
        classified = _failure(
            "artifact-b",
            "deployments",
            name="B",
            deployments=[deployment],
        )
        mock_sync_client.post.return_value = _request_response(
            ["artifact-a"], failed=[classified]
        )
        cause = _server_error("DELETE")
        mock_sync_client.delete.side_effect = cause
        resource = ArtifactResource(mock_sync_client)

        with (
            patch.object(BaseFileHandler, "delete_file", return_value=True),
            pytest.raises(ArtifactBatchDeleteError) as error_info,
        ):
            resource.delete_batch(["artifact-a", "artifact-b"])

        error = error_info.value
        assert error.deleted == []
        assert [failure.artifact_id for failure in error.failed] == ["artifact-b"]
        assert error.failed[0].deployments[0].name == "api"
        assert error.not_completed == ["artifact-a"]

    def test_retry_after_lost_confirmation_reports_not_found(
        self, mock_sync_client: Mock
    ) -> None:
        not_found_a = _failure("artifact-a", "not_found")
        not_found_b = _failure("artifact-b", "not_found")
        mock_sync_client.post.side_effect = [
            {"urls": [], "failed": [not_found_a, not_found_b]},
            {"urls": [], "failed": [not_found_a]},
        ]
        resource = ArtifactResource(mock_sync_client)

        result = resource.delete_batch(["artifact-a", "artifact-b"])

        assert result.deleted == []
        assert [failure.reason for failure in result.failed] == [
            "not_found",
            "not_found",
        ]
        with pytest.raises(ArtifactDeleteError) as error_info:
            resource.delete("artifact-a")
        assert error_info.value.artifact_id == "artifact-a"
        assert error_info.value.reason == "not_found"
        mock_sync_client.delete.assert_not_called()

    def test_delete_returns_none_or_raises_typed_failure(
        self, mock_sync_client: Mock
    ) -> None:
        artifact_id = "artifact-a"
        mock_sync_client.post.return_value = _request_response([artifact_id])
        mock_sync_client.delete.return_value = _confirmation_response([artifact_id])
        resource = ArtifactResource(mock_sync_client)

        with patch.object(BaseFileHandler, "delete_file", return_value=True):
            assert resource.delete(artifact_id) is None

        track = {"id": "track-a", "name": "release"}
        mock_sync_client.post.return_value = {
            "urls": [],
            "failed": [
                _failure(
                    artifact_id,
                    "tracks",
                    name="Artifact A",
                    tracks=[track],
                )
            ],
        }
        with pytest.raises(ArtifactDeleteError) as error_info:
            resource.delete(artifact_id)

        error = error_info.value
        assert error.failure.reason == "tracks"
        assert error.artifact_id == artifact_id
        assert error.name == "Artifact A"
        assert error.tracks[0].id == "track-a"

    def test_delete_propagates_platform_request_error(
        self, mock_sync_client: Mock
    ) -> None:
        cause = _server_error()
        mock_sync_client.post.side_effect = cause
        resource = ArtifactResource(mock_sync_client)

        with pytest.raises(InternalServerError) as error_info:
            resource.delete("artifact-a")

        assert error_info.value is cause

    def test_force_skips_request_and_bucket_and_still_chunks(
        self, mock_sync_client: Mock
    ) -> None:
        artifact_ids = [f"artifact-{index}" for index in range(250)]
        chunks = [artifact_ids[:100], artifact_ids[100:200], artifact_ids[200:]]
        mock_sync_client.delete.side_effect = [
            _confirmation_response(chunk) for chunk in chunks
        ]
        resource = ArtifactResource(mock_sync_client)

        with patch.object(BaseFileHandler, "delete_file") as bucket_delete:
            result = resource.delete_batch(artifact_ids, force=True)

        path = _artifacts_path(mock_sync_client)
        mock_sync_client.post.assert_not_called()
        bucket_delete.assert_not_called()
        assert mock_sync_client.delete.call_args_list == [
            call(path, json={"artifact_ids": chunk, "force": True}) for chunk in chunks
        ]
        assert result.deleted == artifact_ids

    def test_force_does_not_override_tracks(self, mock_sync_client: Mock) -> None:
        artifact_id = "artifact-a"
        track = {"id": "track-a", "name": "release"}
        mock_sync_client.delete.return_value = {
            "deleted": [],
            "failed": [
                _failure(
                    artifact_id,
                    "tracks",
                    name="Artifact A",
                    tracks=[track],
                )
            ],
        }
        resource = ArtifactResource(mock_sync_client)

        with (
            patch.object(BaseFileHandler, "delete_file") as bucket_delete,
            pytest.raises(ArtifactDeleteError) as error_info,
        ):
            resource.delete(artifact_id, force=True)

        mock_sync_client.post.assert_not_called()
        bucket_delete.assert_not_called()
        assert error_info.value.reason == "tracks"
        assert error_info.value.tracks[0].name == "release"

    def test_legacy_manual_sequence_still_finishes_deletion(
        self, mock_sync_client: Mock
    ) -> None:
        artifact_id = "artifact-a"
        legacy_url = "https://storage.example.com/artifact-a"
        mock_sync_client.get.return_value = {"url": legacy_url}
        mock_sync_client.post.return_value = {
            "urls": [_url_entry(artifact_id, "Artifact A")],
            "failed": [],
        }
        mock_sync_client.delete.return_value = _confirmation_response([artifact_id])
        resource = ArtifactResource(mock_sync_client)

        assert resource.delete_url(artifact_id) == {"url": legacy_url}
        with patch.object(
            BaseFileHandler, "delete_file", return_value=True
        ) as bucket_delete:
            assert resource.delete(artifact_id) is None

        bucket_delete.assert_called_once_with(legacy_url)
        mock_sync_client.delete.assert_called_once_with(
            _artifacts_path(mock_sync_client),
            json={"artifact_ids": [artifact_id], "force": False},
        )

    def test_empty_batch_returns_without_requests(self, mock_sync_client: Mock) -> None:
        resource = ArtifactResource(mock_sync_client)

        result = resource.delete_batch([])

        assert result.deleted == []
        assert result.failed == []
        mock_sync_client.post.assert_not_called()
        mock_sync_client.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_three_phases_and_force_failure_parity(
        self, mock_async_client: AsyncMock
    ) -> None:
        artifact_ids = ["artifact-a", "artifact-b"]
        mock_async_client.post.return_value = _request_response(artifact_ids)
        mock_async_client.delete.return_value = _confirmation_response(artifact_ids)
        resource = AsyncArtifactResource(mock_async_client)

        bucket_delete = AsyncMock(return_value=True)
        with patch.object(
            BaseFileHandler,
            "delete_file_async",
            new=bucket_delete,
        ):
            result = await resource.delete_batch(artifact_ids)

        assert result.deleted == artifact_ids
        assert result.failed == []
        assert bucket_delete.await_count == 2
        mock_async_client.post.assert_awaited_once_with(
            f"{_artifacts_path(mock_async_client)}/delete-urls",
            json={"artifact_ids": artifact_ids},
        )
        mock_async_client.delete.assert_awaited_once_with(
            _artifacts_path(mock_async_client),
            json={"artifact_ids": artifact_ids, "force": False},
        )

        mock_async_client.post.reset_mock()
        mock_async_client.delete.reset_mock()
        mock_async_client.delete.return_value = {
            "deleted": [],
            "failed": [
                _failure(
                    "artifact-a",
                    "tracks",
                    tracks=[{"id": "track-a", "name": "release"}],
                )
            ],
        }
        with pytest.raises(ArtifactDeleteError) as error_info:
            await resource.delete("artifact-a", force=True)
        assert error_info.value.reason == "tracks"
        mock_async_client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_async_storage_update_failure_is_best_effort(
        self, mock_async_client: AsyncMock
    ) -> None:
        artifact_id = "artifact-a"
        mock_async_client.post.return_value = _request_response([artifact_id])
        resource = AsyncArtifactResource(mock_async_client)
        update = AsyncMock(side_effect=RuntimeError("update failed"))

        with (
            patch.object(
                BaseFileHandler,
                "delete_file_async",
                new=AsyncMock(return_value=False),
            ),
            patch.object(resource, "update", new=update),
        ):
            result = await resource.delete_batch([artifact_id])

        assert result.deleted == []
        assert result.failed[0].reason == "storage_error"
        update.assert_awaited_once_with(
            artifact_id,
            status=ArtifactStatus.DELETION_FAILED,
            collection_id=mock_async_client.collection,
        )
        mock_async_client.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_async_later_chunk_error_carries_partial_result(
        self, mock_async_client: AsyncMock
    ) -> None:
        artifact_ids = [f"artifact-{index}" for index in range(130)]
        first_chunk = artifact_ids[:100]
        cause = _server_error()
        mock_async_client.post.side_effect = [
            _request_response(first_chunk),
            cause,
        ]
        mock_async_client.delete.return_value = _confirmation_response(first_chunk)
        resource = AsyncArtifactResource(mock_async_client)

        with (
            patch.object(
                BaseFileHandler,
                "delete_file_async",
                new=AsyncMock(return_value=True),
            ),
            pytest.raises(ArtifactBatchDeleteError) as error_info,
        ):
            await resource.delete_batch(artifact_ids)

        assert error_info.value.deleted == first_chunk
        assert error_info.value.not_completed == artifact_ids[100:]
        assert error_info.value.cause is cause
