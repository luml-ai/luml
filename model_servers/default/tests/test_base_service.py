import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from services.service import UvicornService


@pytest.fixture
def post_app() -> tuple[UvicornService, AsyncMock]:
    app = UvicornService()
    handler = AsyncMock(return_value={"ok": True})

    @app.post("/compute")
    async def compute(request_data: dict) -> dict:
        return await handler(request_data)

    return app, handler


@pytest.mark.parametrize("partial_body", [b"", b'{"inputs":'])
async def test_post_disconnect_returns_400_without_running_handler(
    post_app: tuple[UvicornService, AsyncMock], partial_body: bytes
) -> None:
    app, handler = post_app
    messages = []
    if partial_body:
        messages.append({"type": "http.request", "body": partial_body, "more_body": True})
    messages.append({"type": "http.disconnect"})
    receive = AsyncMock(side_effect=[*messages, AssertionError("read after disconnect")])
    send = AsyncMock()

    await app({"type": "http", "method": "POST", "path": "/compute"}, receive, send)

    assert send.call_args_list[0].args[0]["status"] == 400
    assert receive.await_count == len(messages)
    handler.assert_not_awaited()


def test_repeated_disconnect_does_not_starve_event_loop() -> None:
    script = """
import asyncio
from services.service import UvicornService

async def main():
    app = UvicornService()

    @app.post("/compute")
    async def compute(request_data):
        raise AssertionError("handler ran after disconnect")

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            assert message["status"] == 400

    await app({"type": "http", "method": "POST", "path": "/compute"}, receive, send)
    await asyncio.sleep(0)

asyncio.run(main())
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=5)

    assert result.returncode == 0, result.stderr.decode()


@pytest.mark.parametrize("streamed", [False, True])
async def test_post_accepts_body_at_size_limit(
    post_app: tuple[UvicornService, AsyncMock], streamed: bool
) -> None:
    app, handler = post_app
    body = b'{"inputs": {}}'.ljust(16 * 1024 * 1024)
    chunks = [body[: len(body) // 2], body[len(body) // 2 :]] if streamed else [body]
    receive = AsyncMock(
        side_effect=[
            {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
            for i, chunk in enumerate(chunks)
        ]
    )
    send = AsyncMock()

    await app({"type": "http", "method": "POST", "path": "/compute"}, receive, send)

    assert send.call_args_list[0].args[0]["status"] == 200
    handler.assert_awaited_once_with({"inputs": {}})


@pytest.mark.parametrize("body_kind", ["single_chunk", "streamed", "unicode"])
async def test_post_rejects_oversized_body_without_running_handler(
    post_app: tuple[UvicornService, AsyncMock], body_kind: str
) -> None:
    app, handler = post_app
    if body_kind == "unicode":
        body = ('"' + "é" * (8 * 1024 * 1024) + '"').encode()
        assert len(body.decode()) < 16 * 1024 * 1024
    else:
        body = b" " * (16 * 1024 * 1024 + 1)
    chunks = [body[: len(body) // 2], body[len(body) // 2 :]] if body_kind == "streamed" else [body]
    receive = AsyncMock(
        side_effect=[{"type": "http.request", "body": chunk, "more_body": True} for chunk in chunks]
        + [AssertionError("read after exceeding limit")]
    )
    send = AsyncMock()

    await app({"type": "http", "method": "POST", "path": "/compute"}, receive, send)

    assert send.call_args_list[0].args[0]["status"] == 413
    assert receive.await_count == len(chunks)
    handler.assert_not_awaited()


@pytest.mark.parametrize(
    ("chunks", "expected"),
    [
        ([b""], {}),
        ([b'{"inputs":', b"", b' {"value": 1}}'], {"inputs": {"value": 1}}),
        ([b'{"value": "\xc3', b'\xa9"}'], {"value": "é"}),
    ],
)
async def test_post_accepts_complete_body(
    post_app: tuple[UvicornService, AsyncMock], chunks: list[bytes], expected: dict
) -> None:
    app, handler = post_app
    receive = AsyncMock(
        side_effect=[
            {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
            for i, chunk in enumerate(chunks)
        ]
    )
    send = AsyncMock()

    await app({"type": "http", "method": "POST", "path": "/compute"}, receive, send)

    assert send.call_args_list[0].args[0]["status"] == 200
    handler.assert_awaited_once_with(expected)
