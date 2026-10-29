from collections.abc import Awaitable
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from luml_api._exceptions import FileError
from luml_api._types import Artifact, ArtifactStatus
from luml_api.resources.artifacts import ArtifactResource, AsyncArtifactResource

pytestmark = pytest.mark.asyncio


async def _resolve(value: Any) -> Any:  # noqa: ANN401
    return await value if isinstance(value, Awaitable) else value


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    ("filename", "valid"),
    [
        ("model.fnnx", True),
        ("my.model.v2.fnnx", True),
        ("my.model.v2.pyfnx", True),
        ("my.model.v2.dfs", True),
        ("my.model.v2.luml", True),
        ("model.fnnx.txt", False),
        ("model", False),
        ("fnnx", False),
        ("model.", False),
    ],
)
async def test_upload_uses_final_filename_suffix(
    mock_sync_client: Mock,
    mock_async_client: AsyncMock,
    sample_artifact: Artifact,
    asynchronous: bool,
    filename: str,
    valid: bool,
) -> None:
    resource = (
        AsyncArtifactResource(mock_async_client)
        if asynchronous
        else ArtifactResource(mock_sync_client)
    )
    method_mock = AsyncMock if asynchronous else Mock
    created = Mock(artifact=sample_artifact, upload_details=Mock())
    service_name = "AsyncUploadService" if asynchronous else "UploadService"
    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as handler,
        patch(f"luml_api.resources.artifacts.{service_name}") as service,
        patch.object(resource, "create", method_mock(return_value=created)) as create,
        patch.object(
            resource, "update", method_mock(return_value=sample_artifact)
        ) as update,
    ):
        handler.return_value.artifact_details.return_value = Mock(
            file_name=filename,
            extra_values={},
            manifest={},
            file_hash="abc123",
            file_index={},
            size=1024,
        )
        service.return_value.upload_file = method_mock(
            return_value=Mock(status_code=200)
        )
        if valid:
            result = await _resolve(resource.upload(filename))
            assert result is sample_artifact
            assert create.call_args.kwargs["file_name"] == filename
            service.return_value.upload_file.assert_called_once()
            assert update.call_args.kwargs["status"] == ArtifactStatus.UPLOADED
        else:
            with pytest.raises(FileError, match="File format error"):
                await _resolve(resource.upload(filename))
            create.assert_not_called()
            service.assert_not_called()
