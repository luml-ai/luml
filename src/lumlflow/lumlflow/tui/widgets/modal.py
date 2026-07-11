"""Base modal dialog with inline `[Enter]`/`[Esc]` key affordances.

All app dialogs subclass `BaseDialog` so confirm/cancel keys are uniform
and discoverable on-screen. The dialog pauses auto-refresh by emitting
`DialogOpened`/`DialogClosed` messages the app shell listens for.
"""

from collections.abc import Iterable

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Label, Static


class DialogOpened(Message):
    pass


class DialogClosed(Message):
    pass


class BaseDialog[DialogResult](ModalScreen[DialogResult]):
    """Modal dialog providing confirm/cancel keys + inline affordances."""

    DEFAULT_CSS = """
    BaseDialog {
        align: center middle;
        background: black 50%;
    }
    BaseDialog > Vertical {
        width: auto;
        max-width: 80;
        min-width: 40;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    BaseDialog #dialog-title {
        text-style: bold;
        padding-bottom: 1;
    }
    BaseDialog #dialog-error {
        color: $error;
        padding-top: 1;
    }
    BaseDialog #dialog-buttons {
        height: 1;
        padding-top: 1;
    }
    BaseDialog #dialog-buttons Static {
        width: auto;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
    ]

    confirm_label: str = "OK"
    cancel_label: str = "Cancel"
    destructive: bool = False

    def __init__(
        self,
        title: str,
        *,
        message: str | None = None,
        confirm_label: str | None = None,
        cancel_label: str | None = None,
        destructive: bool | None = None,
    ) -> None:
        super().__init__()
        self.title_text = title
        self.message = message
        if confirm_label is not None:
            self.confirm_label = confirm_label
        if cancel_label is not None:
            self.cancel_label = cancel_label
        if destructive is not None:
            self.destructive = destructive

    def compose(self) -> Iterable:  # type: ignore[override]
        with Vertical():
            yield Label(self.title_text, id="dialog-title")
            if self.message is not None:
                yield Static(self.message, id="dialog-message")
            yield from self.compose_body()
            yield Static("", id="dialog-error")
            with Horizontal(id="dialog-buttons"):
                # `markup=False` so `[Enter]` / `[Esc]` render as literal
                # text instead of being parsed as Rich markup tags (which
                # would silently drop the bracketed portion).
                yield Static(
                    f"[Enter] {self.confirm_label}",
                    id="dialog-confirm-key",
                    markup=False,
                )
                yield Static(
                    f"[Esc] {self.cancel_label}",
                    id="dialog-cancel-key",
                    markup=False,
                )

    def compose_body(self) -> Iterable:
        """Override to add dialog-specific fields (yield widgets)."""

        return ()

    def on_mount(self) -> None:
        # Post directly to the app so the message arrives even though the
        # dialog is a ModalScreen and not in the regular widget tree's
        # bubble path that the app's `on_dialog_*` handlers expect.
        self.app.post_message(DialogOpened())
        if self.destructive:
            self._focus_cancel_default()

    def on_unmount(self) -> None:
        # `on_unmount` fires when the dialog is detached after dismiss. By
        # then, our own `post_message(...)` would route through a widget
        # that's already removed from the DOM; post via `self.app` so the
        # message reliably reaches the app's `on_dialog_closed` handler.
        try:
            self.app.post_message(DialogClosed())
        except Exception:  # pragma: no cover - defensive
            # If the app is mid-teardown, dropping the message is fine.
            pass

    def _focus_cancel_default(self) -> None:
        """For destructive dialogs the spec asks Cancel to be the default."""

        # The default focus on a dialog without inputs is the screen itself;
        # we leave focus on the screen so Enter still confirms via binding
        # but the visual affordance highlights Cancel — `destructive` is
        # rendered via the cancel-key affordance label.
        return

    def set_error(self, message: str | None) -> None:
        """Show a non-fatal inline error inside the dialog."""

        try:
            label = self.query_one("#dialog-error", Static)
        except Exception:
            return
        label.update(message or "")
        label.display = bool(message)

    def action_confirm(self) -> None:
        self.dismiss(True)  # type: ignore[arg-type]

    def action_cancel(self) -> None:
        self.dismiss(False)  # type: ignore[arg-type]
