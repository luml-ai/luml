"""Worker delivery keeps app lookup stable without changing callback ownership."""

import asyncio
from unittest.mock import Mock

import pytest
from lumlflow.tui._worker_results import post_worker_result
from textual._context import NoActiveAppError, active_app
from textual.app import App
from textual.events import Callback
from textual.widget import Widget


async def test_result_is_queued_on_owner_and_app_context_is_restored() -> None:
    app = App()
    owner = Widget()
    owner._parent = app
    callback = Mock()

    def enqueue():
        with pytest.raises(LookupError):
            active_app.get()
        assert post_worker_result(owner, callback, 42, label="result")
        with pytest.raises(LookupError):
            active_app.get()

    await asyncio.get_running_loop().run_in_executor(None, enqueue)
    message = owner._message_queue.get_nowait()
    assert isinstance(message, Callback)
    message.callback()
    callback.assert_called_once_with(42, label="result")
    assert app._message_queue.empty()


async def test_result_after_detach_is_dropped() -> None:
    owner = Widget()
    callback = Mock()
    assert not await asyncio.get_running_loop().run_in_executor(
        None, post_worker_result, owner, callback
    )
    assert owner._message_queue.empty()
    callback.assert_not_called()


@pytest.mark.parametrize("error", [NoActiveAppError(), RuntimeError("enqueue failed")])
async def test_enqueue_errors_propagate_and_app_context_is_restored(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    app = App()
    owner = Widget()
    owner._parent = app
    monkeypatch.setattr(owner, "call_later", Mock(side_effect=error))

    def enqueue():
        with pytest.raises(type(error)) as raised:
            post_worker_result(owner, Mock())
        assert raised.value is error
        with pytest.raises(LookupError):
            active_app.get()

    await asyncio.get_running_loop().run_in_executor(None, enqueue)
