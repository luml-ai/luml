import asyncio
import json
import logging
import runpy
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

WORKER_SCRIPT = Path(__file__).resolve().parents[1] / "conda_worker.py"


@pytest.fixture
def load_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[str | None, Mock], dict]:
    def load(source: str | None, handler: Mock) -> dict:
        (tmp_path / "manifest.json").write_text(json.dumps({"variant": "pyfunc"}))
        (tmp_path / "variant_config.json").write_text(json.dumps({"pyfunc_classname": "Model"}))
        if source is not None:
            (tmp_path / "variant_artifacts").mkdir()
            (tmp_path / "variant_artifacts/__pyfunc__.py").write_text(source)
        monkeypatch.setattr(sys, "argv", [str(WORKER_SCRIPT), str(tmp_path)])
        with (
            patch("fnnx.runtime.Runtime", return_value=handler),
            patch("fnnx.device.DeviceMap"),
            patch("fnnx.handlers.local.LocalHandlerConfig"),
        ):
            return runpy.run_path(str(WORKER_SCRIPT))

    return load


@pytest.mark.parametrize(
    ("source", "expected_log"),
    [
        (
            "class Model:\n    async def compute_async(self, i, a):\n        return {}\n",
            "Compute mode SYNC: compute_async has no asynchronous operations",
        ),
        (
            "class Model:\n    async def compute_async(self, i, a):\n        return await work()\n",
            "Compute mode ASYNC: compute_async contains asynchronous operations",
        ),
        (None, "Compute mode UNDECIDED: artifact source unavailable (FileNotFoundError)"),
    ],
)
def test_startup_logs_mode_and_reason_once(
    load_worker: Callable[[str | None, Mock], dict],
    source: str | None,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        load_worker(source, Mock())

    messages = [
        record.getMessage() for record in caplog.records if "Compute mode" in record.message
    ]
    assert messages == [expected_log]


@pytest.mark.parametrize(
    "source",
    [
        "class Model:\n    async def compute_async(self, inputs, attrs):\n"
        "        return self.compute(inputs, attrs)\n",
        "from fnnx import PyFunc\nclass Mixin:\n    pass\n"
        "class SyncBase(PyFunc):\n    async def compute_async(self, inputs, attrs):\n"
        "        return self.compute(inputs, attrs)\n"
        "class Model(Mixin, SyncBase):\n    pass\n",
    ],
)
async def test_sync_compute_keeps_loop_responsive_and_skips_async(
    load_worker: Callable[[str | None, Mock], dict],
    source: str,
) -> None:
    loop_thread = threading.get_ident()
    worker_threads = []

    def compute(inputs: dict, attrs: dict) -> dict:
        worker_threads.append(threading.get_ident())
        time.sleep(1)
        return {"y": inputs["x"] + attrs["offset"]}

    handler = Mock(compute=Mock(side_effect=compute), compute_async=AsyncMock())
    namespace = load_worker(source, handler)
    task = asyncio.create_task(namespace["compute_model"]({"x": 2}, {"offset": 3}))
    ticks = 0
    while not task.done():
        await asyncio.sleep(0.05)
        ticks += 1

    assert await task == {"y": 5}
    assert ticks >= 10
    assert worker_threads and loop_thread not in worker_threads
    handler.compute_async.assert_not_called()


@pytest.mark.parametrize(
    "source",
    [None, "class Model:\n    async def compute_async(self, i, a):\n        return await work()\n"],
)
async def test_runtime_fallback_is_sticky_and_warns_once(
    load_worker: Callable[[str | None, Mock], dict],
    source: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    loop_thread = threading.get_ident()
    worker_threads = []

    def compute(inputs: dict, attrs: dict) -> dict:
        worker_threads.append(threading.get_ident())
        return {"y": inputs["x"]}

    handler = Mock(
        compute=Mock(side_effect=compute), compute_async=AsyncMock(side_effect=NotImplementedError)
    )
    with caplog.at_level(logging.INFO):
        namespace = load_worker(source, handler)
        assert await namespace["compute_model"]({"x": 1}, {}) == {"y": 1}
        assert await namespace["compute_model"]({"x": 2}, {}) == {"y": 2}

    handler.compute_async.assert_awaited_once_with({"x": 1}, {})
    assert len(worker_threads) == 2 and loop_thread not in worker_threads
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert sum("compute mode" in record.getMessage().lower() for record in caplog.records) == 1


async def test_supported_async_requests_never_call_sync(
    load_worker: Callable[[str | None, Mock], dict],
) -> None:
    handler = Mock(compute_async=AsyncMock(return_value={"y": [1, 2]}))
    namespace = load_worker(
        "class Model:\n    async def compute_async(self, i, a):\n        return await work()\n",
        handler,
    )
    assert await namespace["compute_model"]({"x": 1}, {}) == {"y": [1, 2]}
    assert await namespace["compute_model"]({"x": 2}, {}) == {"y": [1, 2]}
    assert handler.compute_async.await_count == 2
    handler.compute.assert_not_called()


async def test_other_async_failures_do_not_retry_or_switch_mode(
    load_worker: Callable[[str | None, Mock], dict],
) -> None:
    handler = Mock(compute_async=AsyncMock(side_effect=ValueError("failed")))
    namespace = load_worker(None, handler)
    for _ in range(2):
        with pytest.raises(ValueError, match="failed"):
            await namespace["compute_model"]({}, {})
    assert handler.compute_async.await_count == 2
    handler.compute.assert_not_called()


async def test_sync_failure_preserves_runtime_fallback(
    load_worker: Callable[[str | None, Mock], dict],
) -> None:
    handler = Mock(
        compute_async=AsyncMock(side_effect=NotImplementedError),
        compute=Mock(side_effect=ValueError("sync failed")),
    )
    namespace = load_worker(None, handler)
    for _ in range(2):
        with pytest.raises(ValueError, match="sync failed"):
            await namespace["compute_model"]({}, {})
    handler.compute_async.assert_awaited_once()
    assert handler.compute.call_count == 2


async def test_in_flight_async_failures_only_warn_once_and_later_requests_skip_async(
    load_worker: Callable[[str | None, Mock], dict], caplog: pytest.LogCaptureFixture
) -> None:
    release = asyncio.Event()
    both_started = asyncio.Event()
    started = 0

    async def compute_async(inputs: dict, attrs: dict) -> dict:
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await release.wait()
        raise NotImplementedError

    handler = Mock(
        compute_async=AsyncMock(side_effect=compute_async), compute=Mock(return_value={"y": 1})
    )
    namespace = load_worker(None, handler)
    with caplog.at_level(logging.WARNING):
        first = asyncio.create_task(namespace["compute_model"]({}, {}))
        second = asyncio.create_task(namespace["compute_model"]({}, {}))
        await asyncio.wait_for(both_started.wait(), timeout=5)
        release.set()
        assert await first == {"y": 1}
        assert await second == {"y": 1}
        assert await namespace["compute_model"]({}, {}) == {"y": 1}

    assert handler.compute_async.await_count == 2
    assert handler.compute.call_count == 3
    assert len(caplog.records) == 1
