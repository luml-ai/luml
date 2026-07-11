from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

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
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
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
            "run-1", "node-1", str(model_file), ["exp-1"],
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
            "run-1", "node-1", str(model_file), ["exp-1"],
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
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.enqueue(
            "run-1", "node-2", str(model_file), ["exp-2"],
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
            "run-1", "node-1", str(model_file), ["exp-1"],
        )
        queue.enqueue(
            "run-1", "node-2", str(model_file), ["exp-2"],
        )
        queue.claim(u1.id)

        resp = await client.get(
            "/api/runs/run-1/uploads?status=pending",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["node_id"] == "node-2"


class TestRetryBehavior:
    @pytest.mark.asyncio
    async def test_failed_upload_retryable_via_endpoint(
        self,
        client: AsyncClient,
        queue: UploadQueue,
        model_file: Path,
    ) -> None:
        upload = queue.enqueue(
            "run-1", "node-1", str(model_file), ["exp-1"],
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
