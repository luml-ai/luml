"""Worker result delivery scoped to the owning widget."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from textual._context import NoActiveAppError, active_app

if TYPE_CHECKING:
    from textual.widget import Widget


def post_worker_result(
    owner: Widget, callback: Callable[..., Any], *args: Any, **kwargs: Any
) -> bool:
    try:
        app = owner.app
    except NoActiveAppError:
        return False
    # keep app lookup stable if the owner detaches inside textual's enqueue.
    token = active_app.set(app)
    try:
        return owner.call_later(callback, *args, **kwargs)
    finally:
        active_app.reset(token)
