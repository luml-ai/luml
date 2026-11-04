import io
import json
import tarfile
from pathlib import Path
from unittest.mock import Mock
from xml.etree import ElementTree as ET

import pytest
from respx import MockRouter
from tests.conftest import TEST_API_KEY, TEST_BASE_URL

from luml_api._client import AsyncLumlClient, LumlClient
from luml_api._exceptions import NotFoundError
from luml_api._types import Artifact, ArtifactStatus

# matches backend/luml/constants.py
USE_MULTIPART_BYTES = 524288000
STORAGE_URL = "https://storage.example.com/model"


@pytest.fixture
def large_model_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "model.fnnx"
    with tarfile.open(file_path, "w") as archive:
        manifest = tarfile.TarInfo("manifest.json")
        manifest.size = 2
        archive.addfile(manifest, io.BytesIO(b"{}"))
    with file_path.open("r+b") as file:
        file.truncate(USE_MULTIPART_BYTES + 1)
    return file_path


@pytest.mark.asyncio
@pytest.mark.respx(base_url=TEST_BASE_URL)
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("multipart_status", [200, 404])
async def test_large_artifact_upload(
    asynchronous: bool,
    multipart_status: int,
    large_model_file: Path,
    mock_initialization_requests: dict,
    sample_artifact: Artifact,
    respx_mock: MockRouter,
) -> None:
    file_size = large_model_file.stat().st_size
    assert file_size > USE_MULTIPART_BYTES
    artifact = sample_artifact.model_copy(
        update={
            "file_name": large_model_file.name,
            "size": file_size,
            "status": ArtifactStatus.PENDING_UPLOAD,
        }
    )
    data = mock_initialization_requests
    artifact_path = (
        f"/v1/organizations/{data['organization'].id}/orbits/{data['orbit'].id}"
        f"/collections/{data['collection'].id}/artifacts"
    )
    create = respx_mock.post(artifact_path).respond(
        200,
        json={
            "artifact": artifact.model_dump(),
            "upload_details": {
                "type": "s3",
                "url": f"{STORAGE_URL}?uploads",
                "multipart": True,
                "bucket_location": artifact.bucket_location,
                "bucket_secret_id": "secret-1",
            },
        },
    )
    initiate = respx_mock.post(f"{STORAGE_URL}?uploads").respond(
        200,
        text='<InitiateMultipartUploadResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        "<UploadId>upload-123</UploadId></InitiateMultipartUploadResult>",
    )
    parts = [
        {
            "part_number": number,
            "url": f"{STORAGE_URL}?partNumber={number}&uploadId=upload-123",
            "start_byte": start,
            "end_byte": min(start + 100 * 1024 * 1024, file_size) - 1,
            "part_size": min(100 * 1024 * 1024, file_size - start),
        }
        for number, start in enumerate(range(0, file_size, 100 * 1024 * 1024), 1)
    ]
    complete_url = f"{STORAGE_URL}?uploadId=upload-123"
    multipart = respx_mock.post("/v1/bucket-secrets/upload/multipart").respond(
        multipart_status,
        json=(
            {
                "type": "s3",
                "upload_id": "upload-123",
                "parts": parts,
                "complete_url": complete_url,
            }
            if multipart_status == 200
            else {"detail": "Not found"}
        ),
    )
    expected_status = (
        ArtifactStatus.UPLOADED
        if multipart_status == 200
        else ArtifactStatus.UPLOAD_FAILED
    )
    update = respx_mock.patch(f"{artifact_path}/{artifact.id}").respond(
        200, json=artifact.model_copy(update={"status": expected_status}).model_dump()
    )
    part_routes = []
    complete = None
    if multipart_status == 200:
        part_routes = [
            respx_mock.put(part["url"]).respond(200, headers={"ETag": f'"{number}"'})
            for number, part in enumerate(parts, 1)
        ]
        complete = respx_mock.post(complete_url).respond(200)

    client: LumlClient | AsyncLumlClient
    if asynchronous:
        client = AsyncLumlClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
        await client.setup_config()
    else:
        client = LumlClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL)
    progress = Mock()

    async def upload() -> Artifact:
        if isinstance(client, AsyncLumlClient):
            return await client.artifacts.upload(
                str(large_model_file), on_progress=progress
            )
        return client.artifacts.upload(str(large_model_file), on_progress=progress)

    if multipart_status == 200:
        result = await upload()
        assert result.status == ArtifactStatus.UPLOADED
        for part, route in zip(parts, part_routes, strict=True):
            assert route.call_count == 1
            request = route.calls.last.request
            assert len(request.content) == part["part_size"]
            assert request.headers["Content-Length"] == str(part["part_size"])
        assert sum(call.args[0] for call in progress.update.call_args_list) == file_size
        assert complete is not None
        assert complete.call_count == 1
        root = ET.fromstring(complete.calls.last.request.content)
        assert [part.findtext("PartNumber") for part in root] == [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        ]
        assert [part.findtext("ETag") for part in root] == [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
        ]
    else:
        with pytest.raises(NotFoundError):
            await upload()

    assert create.call_count == 1
    assert json.loads(create.calls.last.request.content)["size"] == file_size
    assert initiate.call_count == 1
    assert multipart.call_count == 1
    assert json.loads(multipart.calls.last.request.content) == {
        "bucket_id": "secret-1",
        "bucket_location": artifact.bucket_location,
        "size": file_size,
        "upload_id": "upload-123",
    }
    assert update.call_count == 1
    assert json.loads(update.calls.last.request.content) == {
        "status": expected_status.value
    }
