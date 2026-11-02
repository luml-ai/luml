import asyncio
import hashlib
from collections.abc import AsyncGenerator
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import (
    ASGITransport,
    AsyncBaseTransport,
    AsyncByteStream,
    AsyncClient,
    Request,
    Response,
)

from luml_prisma.api import uploads
from luml_prisma.config import load_config
from luml_prisma.server import app
from luml_prisma.services.upload_queue import UploadQueue, UploadStatus


@pytest.fixture
def queue(tmp_path: Path) -> UploadQueue:
    return UploadQueue(tmp_path / "uploads.db")


@pytest.fixture
def model_file(tmp_path: Path) -> Path:
    f = tmp_path / "model.luml"
    f.write_bytes(b"model-data")
    return f


@pytest.fixture
async def client(
    queue: UploadQueue,
) -> AsyncGenerator[AsyncClient, None]:
    app.state.upload_queue = queue
    app.state.config = replace(load_config(), upload_bucket_host="s3.example.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as c:
        yield c


class TestPostUploadUrl:
    @pytest.mark.asyncio
    async def test_returns_202_on_claim(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1",
            "node-1",
            str(model_file),
            ["exp-1"],
        )
        with patch(
            "luml_prisma.api.uploads._do_upload",
            new_callable=AsyncMock,
        ):
            resp = await client.post(
                f"/api/runs/run-1/uploads/{upload.id}/url",
                json={"presigned_url": "https://s3.example.com/upload"},
            )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_returns_409_when_already_claimed(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1",
            "node-1",
            str(model_file),
            ["exp-1"],
        )
        queue.claim(upload.id)

        resp = await client.post(
            f"/api/runs/run-1/uploads/{upload.id}/url",
            json={"presigned_url": "https://s3.example.com/upload"},
        )
        assert resp.status_code == 409
        assert "already claimed" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_returns_409_for_nonexistent(
        self,
        client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/runs/run-1/uploads/nonexistent/url",
            json={"presigned_url": "https://s3.example.com/upload"},
        )
        assert resp.status_code == 409


class TestListUploads:
    @pytest.mark.asyncio
    async def test_returns_pending_uploads(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        queue.enqueue(
            "run-1",
            "node-1",
            str(model_file),
            ["exp-1"],
        )
        queue.enqueue(
            "run-1",
            "node-2",
            str(model_file),
            ["exp-2"],
        )

        resp = await client.get(
            "/api/runs/run-1/uploads?status=pending",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["run_id"] == "run-1"
        assert data[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_pending(
        self,
        client: AsyncClient,
    ) -> None:
        resp = await client.get(
            "/api/runs/run-1/uploads?status=pending",
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_excludes_claimed_uploads(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        u1 = queue.enqueue(
            "run-1",
            "node-1",
            str(model_file),
            ["exp-1"],
        )
        queue.enqueue(
            "run-1",
            "node-2",
            str(model_file),
            ["exp-2"],
        )
        queue.claim(u1.id)

        resp = await client.get(
            "/api/runs/run-1/uploads?status=pending",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["node_id"] == "node-2"


class TestResumeMetadata:
    @pytest.mark.asyncio
    async def test_pending_uploads_carry_manifest_and_file_index(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        tmp_path: Path,
    ) -> None:
        import io
        import json
        import tarfile

        archive = tmp_path / "model.luml"
        with tarfile.open(archive, "w") as tar:
            body = json.dumps({"variant": "pyfunc", "producer_tags": ["x"]}).encode()
            info = tarfile.TarInfo(name="manifest.json")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
        queue.enqueue("run-1", "node-1", str(archive), ["exp-1"])

        resp = await client.get("/api/runs/run-1/uploads?status=pending")

        data = resp.json()[0]
        assert data["manifest"]["variant"] == "pyfunc"
        assert list(data["file_index"]) == ["manifest.json"]

    @pytest.mark.asyncio
    async def test_dismiss_closes_the_upload(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        upload = queue.enqueue("run-1", "node-1", str(model_file), ["exp-1"])

        resp = await client.post(f"/api/runs/run-1/uploads/{upload.id}/dismiss")

        assert resp.status_code == 200
        assert queue.get_pending("run-1") == []
        stored = queue.get(upload.id)
        assert stored is not None
        assert stored.status == UploadStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_dismiss_in_progress_upload_is_409(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        upload = queue.enqueue("run-1", "node-1", str(model_file), ["exp-1"])
        queue.claim(upload.id)

        resp = await client.post(f"/api/runs/run-1/uploads/{upload.id}/dismiss")

        assert resp.status_code == 409
        stored = queue.get(upload.id)
        assert stored is not None
        assert stored.status == UploadStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_dismiss_unknown_upload_is_404(
        self,
        client: AsyncClient,
    ) -> None:
        resp = await client.post("/api/runs/run-1/uploads/nope/dismiss")
        assert resp.status_code == 404


class TestRetryBehavior:
    @pytest.mark.asyncio
    async def test_failed_upload_retryable_via_endpoint(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1",
            "node-1",
            str(model_file),
            ["exp-1"],
        )
        queue.claim(upload.id)
        queue.fail(upload.id, "network error")

        fetched = queue.get(upload.id)
        assert fetched is not None
        assert fetched.status == UploadStatus.PENDING
        assert fetched.retry_count == 1

        with patch(
            "luml_prisma.api.uploads._do_upload",
            new_callable=AsyncMock,
        ):
            resp = await client.post(
                f"/api/runs/run-1/uploads/{upload.id}/url",
                json={"presigned_url": "https://s3.example.com/new-url"},
            )
        assert resp.status_code == 202


@pytest.mark.parametrize(
    "url",
    [
        "http://s3.example.com/upload",
        "https://attacker.example/upload",
        "https://s3.example.com.attacker.example/upload",
        "https://attacker.s3.example.com/upload",
        "https://s3.example.com@attacker.example/upload",
        "https://user:password@s3.example.com/upload",
        "https://s3.example.com:8443/upload",
        "https://s3.example.com/upload#fragment",
        "//s3.example.com/upload",
        "https://[invalid/upload",
        "https://s3.example.com/\nupload",
        " https://s3.example.com/upload",
    ],
)
async def test_rejects_untrusted_url_without_claiming(
    client: AsyncClient,
    queue: UploadQueue,
    model_file: Path,
    url: str,
) -> None:
    upload = queue.enqueue("run-1", "node-1", str(model_file), [])
    with patch.object(uploads, "_do_upload", new_callable=AsyncMock) as do_upload:
        response = await client.post(
            f"/api/runs/run-1/uploads/{upload.id}/url",
            json={"presigned_url": url},
        )
    assert response.status_code == 422
    do_upload.assert_not_called()
    stored = queue.get(upload.id)
    assert stored is not None
    assert stored.status == UploadStatus.PENDING
    assert stored.retry_count == 0


async def test_upload_requires_configured_bucket_host(
    client: AsyncClient,
    queue: UploadQueue,
    model_file: Path,
) -> None:
    app.state.config = replace(app.state.config, upload_bucket_host="")
    upload = queue.enqueue("run-1", "node-1", str(model_file), [])
    response = await client.post(
        f"/api/runs/run-1/uploads/{upload.id}/url",
        json={"presigned_url": "https://s3.example.com/upload"},
    )
    assert response.status_code == 503
    stored = queue.get(upload.id)
    assert stored is not None
    assert stored.status == UploadStatus.PENDING


async def test_upload_task_is_retained_until_finished(
    client: AsyncClient,
    queue: UploadQueue,
    model_file: Path,
) -> None:
    upload = queue.enqueue("run-1", "node-1", str(model_file), [])
    finished = asyncio.Event()

    async def wait_upload(**kwargs: object) -> None:
        await finished.wait()

    with patch.object(uploads, "_do_upload", side_effect=wait_upload):
        response = await client.post(
            f"/api/runs/run-1/uploads/{upload.id}/url",
            json={"presigned_url": "https://S3.EXAMPLE.COM:443/upload?signature=x"},
        )
        assert response.status_code == 202
        assert len(uploads._upload_tasks) == 1
        task = next(iter(uploads._upload_tasks))
        assert not task.done()
        finished.set()
        await task
        await asyncio.sleep(0)
        assert uploads._upload_tasks == set()


@pytest.mark.parametrize("status_code", [200, 403, 307])
async def test_upload_streams_bounded_chunks(
    queue: UploadQueue,
    model_file: Path,
    status_code: int,
) -> None:
    data = bytes(range(256)) * 2049
    model_file.write_bytes(data)
    upload = queue.enqueue("run-1", "node-1", str(model_file), [])
    assert queue.claim(upload.id)
    engine = Mock()
    received_hash = hashlib.sha256()
    sizes = []

    class Transport(AsyncBaseTransport):
        async def handle_async_request(self, request: Request) -> Response:
            assert request.headers["content-type"] == "application/octet-stream"
            assert request.headers["content-length"] == str(len(data))
            assert "transfer-encoding" not in request.headers
            assert isinstance(request.stream, AsyncByteStream)
            async for chunk in request.stream:
                sizes.append(len(chunk))
                received_hash.update(chunk)
            return Response(
                status_code,
                headers={"Location": "https://attacker.example/upload"},
            )

    storage_client = AsyncClient(transport=Transport())
    with patch(
        "luml_prisma.api.uploads.httpx.AsyncClient",
        return_value=storage_client,
    ) as create_client:
        await uploads._do_upload(
            queue,
            upload.id,
            str(model_file),
            "https://s3.example.com/upload",
            engine,
            "run-1",
            "node-1",
        )
    create_client.assert_called_once_with(follow_redirects=False)

    assert len(sizes) > 1
    assert max(sizes) <= 64 * 1024
    assert sum(sizes) == len(data)
    assert received_hash.digest() == hashlib.sha256(data).digest()
    stored = queue.get(upload.id)
    assert stored is not None
    if status_code == 200:
        assert stored.status == UploadStatus.COMPLETED
        assert engine._emit_event.call_args.args[2] == "upload_completed"
    else:
        assert stored.status == UploadStatus.PENDING
        assert stored.retry_count == 1
        assert engine._emit_event.call_args.args[2] == "upload_failed"


@pytest.mark.parametrize("file_exists", [True, False])
async def test_upload_empty_or_missing_file_fails_without_request(
    queue: UploadQueue,
    model_file: Path,
    file_exists: bool,
) -> None:
    if file_exists:
        model_file.write_bytes(b"")
    else:
        model_file.unlink()
    upload = queue.enqueue("run-1", "node-1", str(model_file), [])
    assert queue.claim(upload.id)
    with patch("luml_prisma.api.uploads.httpx.AsyncClient") as storage_client:
        await uploads._do_upload(
            queue,
            upload.id,
            str(model_file),
            "https://s3.example.com/upload",
            None,
            "run-1",
            "node-1",
        )
    storage_client.assert_not_called()
    stored = queue.get(upload.id)
    assert stored is not None
    assert stored.status == UploadStatus.PENDING
    assert stored.retry_count == 1
