"""Toast notification host.

Toasts are stackable, auto-dismiss after a short delay, and are styled by
severity. The host is mounted once at the app level and exposes a single
`notify` method that screens/dialogs use.
"""

from collections.abc import Callable
from typing import Literal

from textual.containers import Vertical
from textual.widgets import Static

ToastSeverity = Literal["info", "success", "warning", "error"]


class _Toast(Static):
    DEFAULT_CSS = """
    _Toast {
        width: auto;
        min-width: 32;
        max-width: 60;
        height: auto;
        padding: 0 2;
        margin: 1 2 0 0;
        border: round $primary;
        background: $surface;
        color: $foreground;
    }
    _Toast.-info {
        border: round $accent;
    }
    _Toast.-success {
        border: round $success;
    }
    _Toast.-warning {
        border: round $warning;
    }
    _Toast.-error {
        border: round $error;
    }
    """

    def __init__(self, message: str, severity: ToastSeverity) -> None:
        super().__init__(message)
        self.add_class(f"-{severity}")


class ToastHost(Vertical):
    DEFAULT_CSS = """
    ToastHost {
        layer: toast;
        dock: right;
        align: right top;
        width: auto;
        height: auto;
        background: transparent;
    }
    """

    DEFAULT_DURATION: float = 4.0

    def push_toast(
        self,
        message: str,
        *,
        severity: ToastSeverity = "info",
        duration: float | None = None,
    ) -> _Toast:
        toast = _Toast(message, severity)
        self.mount(toast)
        delay = duration if duration is not None else self.DEFAULT_DURATION
        self.set_timer(delay, _dismiss(toast))
        return toast


def _dismiss(toast: _Toast) -> Callable[[], None]:
    def _do() -> None:
        if toast.is_mounted:
            toast.remove()

    return _do
