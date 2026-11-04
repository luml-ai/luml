import asyncio
import json

import anyio.to_thread
import httpx
import pytest
from fastapi import FastAPI
from lumlflow.api import luml
from lumlflow.infra.progress_store import ProgressStore


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> ProgressStore:
    store = ProgressStore()
    monkeypatch.setattr(luml, "progress_store", store)
    return store


@pytest.mark.parametrize("status", ["complete", "error"])
async def test_running_upload_polls_without_worker_threads(
    store: ProgressStore, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    def run_in_worker(*args, **kwargs):
        pytest.fail("upload progress streaming used a threadpool worker")

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_in_worker)
    store.create("job")
    stream = luml.upload_progress("job").body_iterator
    assert await anext(stream) == 'data: {"type": "progress", "percent": 0}\n\n'

    polled = asyncio.Event()
    get = store.get
    polls = 0

    def track_polls(job_id: str):
        nonlocal polls
        polls += 1
        if polls >= 2:
            polled.set()
        return get(job_id)

    monkeypatch.setattr(store, "get", track_polls)
    pending = asyncio.create_task(anext(stream))
    try:
        await asyncio.wait_for(polled.wait(), timeout=2)
        assert not pending.done()
        store.update_progress("job", 50)
        assert await asyncio.wait_for(pending, timeout=2) == (
            'data: {"type": "progress", "percent": 50}\n\n'
        )
        pending = asyncio.create_task(anext(stream))
        await asyncio.sleep(0)
        if status == "complete":
            store.set_complete("job", [])
            expected = {"type": "complete", "artifacts": []}
        else:
            store.set_error("job", "upload failed")
            expected = {"type": "error", "message": "upload failed"}
        event = await asyncio.wait_for(pending, timeout=2)
        assert json.loads(event.removeprefix("data: ")) == expected
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
        assert store.get("job") is None
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await stream.aclose()


@pytest.mark.parametrize("status", ["complete", "error", "not_found"])
async def test_terminal_upload_events(store: ProgressStore, status: str) -> None:
    if status != "not_found":
        store.create("job")
    if status == "complete":
        store.set_complete("job", [{"id": "artifact"}])
        expected = {"type": "complete", "artifacts": [{"id": "artifact"}]}
    elif status == "error":
        store.set_error("job", "upload failed")
        expected = {"type": "error", "message": "upload failed"}
    else:
        expected = {"type": "not_found"}

    app = FastAPI()
    app.include_router(luml.luml_router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/luml/artifact/job/progress")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text.startswith("data: ")
    assert response.text.endswith("\n\n")
    assert json.loads(response.text.removeprefix("data: ")) == expected
    assert store.get("job") is None


async def test_cancelling_upload_stream_keeps_running_job(store: ProgressStore) -> None:
    store.create("job")
    stream = luml.upload_progress("job").body_iterator
    await anext(stream)
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending, timeout=1)
    assert store.get("job") is not None
    await stream.aclose()
