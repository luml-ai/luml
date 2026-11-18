from __future__ import annotations

from typing import TYPE_CHECKING

from textual._context import NoActiveAppError

if TYPE_CHECKING:
    from textual.widget import Widget

    from lumlflow.tui.data import DataFacade


def resolve_facade(widget: Widget, explicit: DataFacade | None) -> DataFacade | None:
    if explicit is not None:
        return explicit
    try:
        app = widget.app
    except NoActiveAppError:
        return None
    return getattr(app, "_facade", None)
