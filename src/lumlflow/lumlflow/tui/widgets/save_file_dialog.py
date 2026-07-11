"""SaveFileDialog — a simple text-input dialog for choosing a save path.

Used by the Attachments tab's save-to-disk action: the user is shown a
prefilled path (default: the attachment's basename in the current
working directory) and confirms or edits it before bytes are written.

The dialog returns the chosen path as a string, or `None` if the user
cancelled. Validation is minimal — empty path is rejected with an
inline error; everything else is left to the file-writer to surface as
a toast (permissions, missing parent dir, etc.).
"""

from __future__ import annotations

from collections.abc import Iterable

from textual.binding import Binding
from textual.widgets import Input, Label

from lumlflow.tui.widgets.modal import BaseDialog
from lumlflow.tui.widgets.path_suggester import PathSuggester


class SaveFileDialog(BaseDialog[str | None]):
    """Prompt for a save-to-disk destination path."""

    DEFAULT_CSS = """
    SaveFileDialog .field-label {
        padding-top: 1;
    }
    SaveFileDialog Input {
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Save", show=False),
    ]

    confirm_label = "Save"
    cancel_label = "Cancel"

    def __init__(
        self,
        *,
        title: str,
        default_path: str = "",
    ) -> None:
        super().__init__(title=title)
        self._default_path = default_path

    def compose_body(self) -> Iterable:
        yield Label("Save to (path · → completes)", classes="field-label")
        yield Input(
            value=self._default_path,
            placeholder="/path/to/save/here",
            id="save-path-input",
            suggester=PathSuggester(),
        )

    def on_mount(self) -> None:
        super().on_mount()
        try:
            self.query_one("#save-path-input", Input).focus()
        except Exception:
            pass

    def action_confirm(self) -> None:
        try:
            path_input = self.query_one("#save-path-input", Input)
        except Exception:
            self.dismiss(None)
            return
        path_value = path_input.value.strip()
        if not path_value:
            self.set_error("A path is required.")
            path_input.focus()
            return
        self.dismiss(path_value)

    def action_cancel(self) -> None:
        self.dismiss(None)


__all__ = ("SaveFileDialog",)
