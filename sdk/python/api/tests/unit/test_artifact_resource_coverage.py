from collections.abc import Callable
from unittest.mock import AsyncMock, Mock, patch

import pytest

from luml_api._exceptions import FileError, FileUploadError
from luml_api._types import (
    Artifact,
    ArtifactStatus,
    ArtifactType,
    BucketType,
)
from luml_api.resources.artifacts import (
    ArtifactResource,
    ArtifactResourceBase,
    AsyncArtifactResource,
)

VALID_UUID = "0199c337-09f4-7a01-9f5f-5f68a562cf70"


def _created_artifact_payload(sample_artifact: Artifact) -> dict:
    return {
        "upload_details": {
            "type": BucketType.S3,
            "url": "https://example.com/upload",
            "multipart": False,
            "bucket_location": "test/location",
            "bucket_secret_id": "0199c455-21ef-79d9-9dfc-fec3d72bf4b5",
        },
        "artifact": sample_artifact.model_dump(),
    }


def _artifact_details_mock() -> Mock:
    return Mock(
        file_name="model.fnnx",
        extra_values={},
        manifest={},
        file_hash="abc123",
        file_index={},
        size=1024,
    )


# --------------------------------------------------------------------------- #
# Abstract base class
# --------------------------------------------------------------------------- #
def test_abstract_base_methods_raise_not_implemented() -> None:
    # Instantiate the ABC by clearing its abstract markers so the default
    # (NotImplementedError-raising) method bodies can be exercised directly.
    impl = type("_Impl", (ArtifactResourceBase,), {})
    impl.__abstractmethods__ = frozenset()  # type: ignore[attr-defined]
    obj = impl()

    calls: list[Callable[[], object]] = [
        lambda: obj.get("v"),
        lambda: obj._get_by_name(None, "n"),
        lambda: obj._get_by_id(None, "i"),
        lambda: obj.list(),
        lambda: obj.download_url("a"),
        lambda: obj.delete_url("a"),
        lambda: obj.upload("f"),
        lambda: obj.download("a"),
        lambda: obj.create(None, "f", {}, {}, "h", {}, 1, "n"),
        lambda: obj.update("a"),
        lambda: obj.delete("a"),
    ]
    for call in calls:
        with pytest.raises(NotImplementedError):
            call()


# --------------------------------------------------------------------------- #
# get by id / _get_by_id
# --------------------------------------------------------------------------- #
def test_get_by_uuid(mock_sync_client: Mock, sample_artifact: Artifact) -> None:
    mock_sync_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }
    resource = ArtifactResource(mock_sync_client)

    artifact = resource.get(VALID_UUID)

    assert artifact is not None
    assert artifact.id == VALID_UUID


def test_get_by_uuid_not_found(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = {"items": [], "cursor": None}
    resource = ArtifactResource(mock_sync_client)

    assert resource.get("00000000-0000-0000-0000-000000000000") is None


@pytest.mark.asyncio
async def test_async_get_by_uuid(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    mock_async_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }
    resource = AsyncArtifactResource(mock_async_client)

    artifact = await resource.get(VALID_UUID)

    assert artifact is not None
    assert artifact.id == VALID_UUID


@pytest.mark.asyncio
async def test_async_get_by_uuid_not_found(mock_async_client: AsyncMock) -> None:
    mock_async_client.get.return_value = {"items": [], "cursor": None}
    resource = AsyncArtifactResource(mock_async_client)

    assert await resource.get("00000000-0000-0000-0000-000000000000") is None


# --------------------------------------------------------------------------- #
# list with optional params
# --------------------------------------------------------------------------- #
def test_list_with_all_params(
    mock_sync_client: Mock, sample_artifact: Artifact
) -> None:
    mock_sync_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }
    resource = ArtifactResource(mock_sync_client)

    resource.list(
        start_after="cursor-1", sort_by="F1", types=[ArtifactType.MODEL]
    )

    params = mock_sync_client.get.call_args.kwargs["params"]
    assert params["cursor"] == "cursor-1"
    assert params["sort_by"] == "F1"
    assert params["types"] == ["model"]


@pytest.mark.asyncio
async def test_async_list_with_all_params(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    mock_async_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }
    resource = AsyncArtifactResource(mock_async_client)

    await resource.list(
        start_after="cursor-1", sort_by="F1", types=[ArtifactType.MODEL]
    )

    params = mock_async_client.get.call_args.kwargs["params"]
    assert params["cursor"] == "cursor-1"
    assert params["sort_by"] == "F1"
    assert params["types"] == ["model"]


# --------------------------------------------------------------------------- #
# list_all auto-pagination
# --------------------------------------------------------------------------- #
def test_list_all(mock_sync_client: Mock, sample_artifact: Artifact) -> None:
    mock_sync_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }
    resource = ArtifactResource(mock_sync_client)

    items = list(resource.list_all())

    assert len(items) == 1
    assert items[0].id == sample_artifact.id


@pytest.mark.asyncio
async def test_async_list_all(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    mock_async_client.get.return_value = {
        "items": [sample_artifact.model_dump()],
        "cursor": None,
    }
    resource = AsyncArtifactResource(mock_async_client)

    items = [item async for item in resource.list_all()]

    assert len(items) == 1
    assert items[0].id == sample_artifact.id


# --------------------------------------------------------------------------- #
# upload: invalid file format
# --------------------------------------------------------------------------- #
def test_upload_invalid_format(mock_sync_client: Mock) -> None:
    resource = ArtifactResource(mock_sync_client)
    with patch("luml_api.resources.artifacts.ModelFileHandler") as handler_cls:
        handler_cls.return_value.artifact_details.return_value = Mock(
            file_name="model.txt"
        )
        with pytest.raises(FileError, match="File format error"):
            resource.upload("model.txt")


@pytest.mark.asyncio
async def test_async_upload_invalid_format(mock_async_client: AsyncMock) -> None:
    resource = AsyncArtifactResource(mock_async_client)
    with patch("luml_api.resources.artifacts.ModelFileHandler") as handler_cls:
        handler_cls.return_value.artifact_details.return_value = Mock(
            file_name="model.txt"
        )
        with pytest.raises(FileError, match="File format error"):
            await resource.upload("model.txt")


# --------------------------------------------------------------------------- #
# upload: failure marks artifact UPLOAD_FAILED and re-raises
# --------------------------------------------------------------------------- #
def test_upload_failure_marks_failed(
    mock_sync_client: Mock, sample_artifact: Artifact
) -> None:
    mock_sync_client.post.return_value = _created_artifact_payload(sample_artifact)
    mock_sync_client.patch.return_value = sample_artifact.model_dump()
    resource = ArtifactResource(mock_sync_client)

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as handler_cls,
        patch("luml_api.resources.artifacts.UploadService") as service_cls,
    ):
        handler_cls.return_value.artifact_details.return_value = (
            _artifact_details_mock()
        )
        service_cls.return_value.upload_file.side_effect = FileUploadError("boom")

        with pytest.raises(FileUploadError, match="boom"):
            resource.upload("model.fnnx")

    patch_json = mock_sync_client.patch.call_args.kwargs["json"]
    assert patch_json["status"] == ArtifactStatus.UPLOAD_FAILED.value


@pytest.mark.asyncio
async def test_async_upload_failure_marks_failed(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    mock_async_client.post.return_value = _created_artifact_payload(sample_artifact)
    mock_async_client.patch.return_value = sample_artifact.model_dump()
    resource = AsyncArtifactResource(mock_async_client)

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as handler_cls,
        patch("luml_api.resources.artifacts.AsyncUploadService") as service_cls,
    ):
        handler_cls.return_value.artifact_details.return_value = (
            _artifact_details_mock()
        )
        service_cls.return_value.upload_file = AsyncMock(
            side_effect=FileUploadError("boom")
        )

        with pytest.raises(FileUploadError, match="boom"):
            await resource.upload("model.fnnx")

    patch_json = mock_async_client.patch.call_args.kwargs["json"]
    assert patch_json["status"] == ArtifactStatus.UPLOAD_FAILED.value


def test_upload_success_marks_uploaded(
    mock_sync_client: Mock, sample_artifact: Artifact
) -> None:
    mock_sync_client.post.return_value = _created_artifact_payload(sample_artifact)
    mock_sync_client.patch.return_value = sample_artifact.model_dump()
    resource = ArtifactResource(mock_sync_client)

    with (
        patch("luml_api.resources.artifacts.ModelFileHandler") as handler_cls,
        patch("luml_api.resources.artifacts.UploadService") as service_cls,
    ):
        handler_cls.return_value.artifact_details.return_value = (
            _artifact_details_mock()
        )
        service_cls.return_value.upload_file.return_value = Mock(status_code=200)

        resource.upload("model.fnnx")

    patch_json = mock_sync_client.patch.call_args.kwargs["json"]
    assert patch_json["status"] == ArtifactStatus.UPLOADED.value


# --------------------------------------------------------------------------- #
# download
# --------------------------------------------------------------------------- #
def test_download_with_explicit_path(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = {"url": "https://example.com/file"}
    resource = ArtifactResource(mock_sync_client)

    with patch("luml_api.resources.artifacts.S3FileHandler") as handler_cls:
        resource.download(VALID_UUID, file_path="/tmp/out.fnnx")

    handler_cls.return_value.download_file_with_progress.assert_called_once()
    kwargs = handler_cls.return_value.download_file_with_progress.call_args.kwargs
    assert kwargs["file_path"] == "/tmp/out.fnnx"
    assert kwargs["url"] == "https://example.com/file"


def test_download_resolves_filename_when_path_none(
    mock_sync_client: Mock, sample_artifact: Artifact
) -> None:
    mock_sync_client.get.side_effect = [
        {"items": [sample_artifact.model_dump()], "cursor": None},
        {"url": "https://example.com/file"},
    ]
    resource = ArtifactResource(mock_sync_client)

    with patch("luml_api.resources.artifacts.S3FileHandler") as handler_cls:
        resource.download(VALID_UUID)

    kwargs = handler_cls.return_value.download_file_with_progress.call_args.kwargs
    assert kwargs["file_path"] == sample_artifact.file_name


def test_download_artifact_not_found(mock_sync_client: Mock) -> None:
    mock_sync_client.get.return_value = {"items": [], "cursor": None}
    resource = ArtifactResource(mock_sync_client)

    with pytest.raises(ValueError, match="not found"):
        resource.download(VALID_UUID)


@pytest.mark.asyncio
async def test_async_download_with_explicit_path(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get.return_value = {"url": "https://example.com/file"}
    resource = AsyncArtifactResource(mock_async_client)

    with patch("luml_api.resources.artifacts.S3FileHandler") as handler_cls:
        await resource.download(VALID_UUID, file_path="/tmp/out.fnnx")

    kwargs = handler_cls.return_value.download_file_with_progress.call_args.kwargs
    assert kwargs["file_path"] == "/tmp/out.fnnx"


@pytest.mark.asyncio
async def test_async_download_resolves_filename_when_path_none(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    mock_async_client.get.side_effect = [
        {"items": [sample_artifact.model_dump()], "cursor": None},
        {"url": "https://example.com/file"},
    ]
    resource = AsyncArtifactResource(mock_async_client)

    with patch("luml_api.resources.artifacts.S3FileHandler") as handler_cls:
        await resource.download(VALID_UUID)

    kwargs = handler_cls.return_value.download_file_with_progress.call_args.kwargs
    assert kwargs["file_path"] == sample_artifact.file_name


@pytest.mark.asyncio
async def test_async_download_artifact_not_found(
    mock_async_client: AsyncMock,
) -> None:
    mock_async_client.get.return_value = {"items": [], "cursor": None}
    resource = AsyncArtifactResource(mock_async_client)

    with pytest.raises(ValueError, match="not found"):
        await resource.download(VALID_UUID)


# --------------------------------------------------------------------------- #
# update: deprecated file_name warning
# --------------------------------------------------------------------------- #
def test_update_file_name_deprecation_warning(
    mock_sync_client: Mock, sample_artifact: Artifact
) -> None:
    mock_sync_client.patch.return_value = sample_artifact.model_dump()
    resource = ArtifactResource(mock_sync_client)

    with pytest.warns(DeprecationWarning, match="file_name"):
        resource.update(VALID_UUID, file_name="ignored.fnnx", name="new-name")


@pytest.mark.asyncio
async def test_async_update_file_name_deprecation_warning(
    mock_async_client: AsyncMock, sample_artifact: Artifact
) -> None:
    mock_async_client.patch.return_value = sample_artifact.model_dump()
    resource = AsyncArtifactResource(mock_async_client)

    with pytest.warns(DeprecationWarning, match="file_name"):
        await resource.update(VALID_UUID, file_name="ignored.fnnx", name="new-name")
