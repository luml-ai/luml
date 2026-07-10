"""Reusable modal dialogs for edit / confirm flows.

`EditEntityDialog` is a generic name/description/tags editor that fits
the `Update*` schema shape shared by groups, experiments, and models.
`ConfirmDialog` is a destructive-action confirm with inline error
display for handler constraint failures (e.g. `409 Cannot delete a
group that has linked experiments`).
`FilterEditorDialog` is the advanced filter DSL editor with live
validation against a caller-supplied validator (typically a
handler's `validate_*` method via the facade).
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Label, Static

from lumlflow.tui.widgets.modal import BaseDialog


@dataclass(frozen=True)
class EntityEditResult:
    """The submitted name / description / tags from `EditEntityDialog`.

    Each field is `None` if it was left unchanged (so callers can build
    a partial `UpdateGroup` / `UpdateExperiment` without touching
    unrelated fields).
    """

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


def _tags_to_string(tags: list[str] | None) -> str:
    if not tags:
        return ""
    return ", ".join(tags)


def _string_to_tags(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


class EditEntityDialog(BaseDialog[EntityEditResult | None]):
    """Edit name / description / tags of an entity.

    Used by Groups, Experiments and Models — the only place this differs
    is the title shown at the top and the initial values pre-filled.
    """

    DEFAULT_CSS = """
    EditEntityDialog .field-label {
        padding-top: 1;
    }
    EditEntityDialog Input {
        margin-bottom: 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "confirm", "Save", show=False),
    ]

    confirm_label = "Save"
    cancel_label = "Cancel"

    def __init__(
        self,
        *,
        title: str,
        name: str = "",
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        super().__init__(title=title)
        self._initial_name = name
        self._initial_description = description or ""
        self._initial_tags = tags or []

    def compose_body(self) -> Iterable:
        yield Label("Name", classes="field-label")
        yield Input(
            value=self._initial_name,
            placeholder="Name",
            id="edit-name",
        )
        yield Label("Description", classes="field-label")
        yield Input(
            value=self._initial_description,
            placeholder="Description",
            id="edit-description",
        )
        yield Label("Tags (comma separated)", classes="field-label")
        yield Input(
            value=_tags_to_string(self._initial_tags),
            placeholder="tag-1, tag-2",
            id="edit-tags",
        )

    def on_mount(self) -> None:
        super().on_mount()
        # Place focus on the name input by default so typing edits the field
        # immediately. The modeless rule still applies: letters typed in this
        # input are literal, not global commands.
        try:
            self.query_one("#edit-name", Input).focus()
        except Exception:
            pass

    def action_confirm(self) -> None:
        name_input = self.query_one("#edit-name", Input)
        desc_input = self.query_one("#edit-description", Input)
        tags_input = self.query_one("#edit-tags", Input)

        new_name = name_input.value.strip()
        if not new_name:
            self.set_error("Name is required.")
            name_input.focus()
            return

        result = EntityEditResult(
            name=new_name if new_name != self._initial_name else None,
            description=(
                desc_input.value.strip() or None
                if desc_input.value.strip() != self._initial_description
                else None
            ),
            tags=(
                _string_to_tags(tags_input.value)
                if _string_to_tags(tags_input.value) != self._initial_tags
                else None
            ),
        )
        # If nothing actually changed, still close (no-op).
        self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmDialog(BaseDialog[bool]):
    """Yes/no confirm dialog with inline error display.

    Defaults focus visually to Cancel for destructive actions (the
    label shows `[Esc] Cancel` first so the eye lands on the safe
    option). The handler's constraint message (e.g. "Cannot delete a
    group that has linked experiments") is surfaced via `set_error`
    when the parent screen receives a 409 from the facade.
    """

    DEFAULT_CSS = """
    ConfirmDialog Static#dialog-message {
        padding-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        title: str,
        message: str,
        confirm_label: str = "Delete",
        cancel_label: str = "Cancel",
        destructive: bool = True,
    ) -> None:
        super().__init__(
            title=title,
            message=message,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            destructive=destructive,
        )

    def compose(self) -> Iterable:  # type: ignore[override]
        # We need to render the buttons with Cancel-first for destructive
        # confirms so the eye lands on the safe option.
        with Vertical():
            yield Label(self.title_text, id="dialog-title")
            if self.message is not None:
                yield Static(self.message, id="dialog-message")
            yield Static("", id="dialog-error")
            with Horizontal(id="dialog-buttons"):
                # `markup=False` so the literal `[Esc]` / `[Enter]` text
                # renders as-is instead of being parsed as Rich markup
                # tags (which would silently drop the bracketed portion).
                if self.destructive:
                    yield Static(
                        f"[Esc] {self.cancel_label}",
                        id="dialog-cancel-key",
                        markup=False,
                    )
                    yield Static(
                        f"[Enter] {self.confirm_label}",
                        id="dialog-confirm-key",
                        markup=False,
                    )
                else:
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


class SortChooserDialog(BaseDialog["SortChooserResult | None"]):
    """Tiny picker for sort field + order on list screens.

    The field set is screen-specific (Groups uses `name`/`created_at`/
    etc.) so callers pass the option labels and ids. Active selection
    is highlighted so the user can tell the current order at a glance.
    """

    DEFAULT_CSS = """
    SortChooserDialog .field-label {
        padding-top: 1;
        text-style: bold;
    }
    SortChooserDialog #sort-fields, SortChooserDialog #sort-orders {
        padding: 0 0 0 0;
    }
    SortChooserDialog .sort-row {
        height: 1;
    }
    SortChooserDialog .sort-active {
        text-style: bold;
        color: $accent;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("j", "move_down", "Down", show=False),
        Binding("o", "toggle_order", "Toggle order", show=False),
    ]

    confirm_label = "Apply"
    cancel_label = "Cancel"

    def __init__(
        self,
        *,
        title: str,
        fields: list[tuple[str, str]],
        current_field: str,
        current_order: str = "desc",
    ) -> None:
        super().__init__(title=title)
        self._fields = fields
        self._current_field = current_field
        self._current_order = current_order
        self._selected_index = next(
            (i for i, (fid, _) in enumerate(fields) if fid == current_field),
            0,
        )

    def compose_body(self) -> Iterable:
        yield Label("Field", classes="field-label")
        with Vertical(id="sort-fields"):
            for fid, label in self._fields:
                yield Static(self._format_field_row(fid, label), classes="sort-row")
        yield Label("Order  [o] toggle", classes="field-label")
        yield Static(self._format_order_row(), id="sort-order-row", classes="sort-row")

    def _format_field_row(self, fid: str, label: str) -> str:
        marker = "●" if fid == self._selected_field_id() else "○"
        return f"{marker} {label}"

    def _format_order_row(self) -> str:
        return f"{'↓ desc' if self._current_order == 'desc' else '↑ asc'}"

    def _selected_field_id(self) -> str:
        if 0 <= self._selected_index < len(self._fields):
            return self._fields[self._selected_index][0]
        return self._current_field

    def _refresh(self) -> None:
        try:
            container = self.query_one("#sort-fields", Vertical)
            rows = list(container.query(Static))
            for idx, ((fid, label), node) in enumerate(
                zip(self._fields, rows, strict=False)
            ):
                node.update(self._format_field_row(fid, label))
                if idx == self._selected_index:
                    node.add_class("sort-active")
                else:
                    node.remove_class("sort-active")
            order_row = self.query_one("#sort-order-row", Static)
            order_row.update(self._format_order_row())
        except Exception:
            pass

    def on_mount(self) -> None:
        super().on_mount()
        self._refresh()

    def action_move_up(self) -> None:
        if self._fields:
            self._selected_index = (self._selected_index - 1) % len(self._fields)
            self._refresh()

    def action_move_down(self) -> None:
        if self._fields:
            self._selected_index = (self._selected_index + 1) % len(self._fields)
            self._refresh()

    def action_toggle_order(self) -> None:
        self._current_order = "asc" if self._current_order == "desc" else "desc"
        self._refresh()

    def action_confirm(self) -> None:
        self.dismiss(
            SortChooserResult(
                field=self._selected_field_id(),
                order=self._current_order,
            )
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


@dataclass(frozen=True)
class SortChooserResult:
    """The chosen sort field id and order ('asc'/'desc')."""

    field: str
    order: str


@dataclass(frozen=True)
class FilterValidation:
    """Live-validation result returned by the validator callback."""

    valid: bool
    error: str | None = None


class FilterEditorDialog(BaseDialog["str | None"]):
    """Advanced filter DSL editor with live validation.

    The caller supplies a `validator(query: str | None) -> FilterValidation`
    callback; the dialog calls it on every input change and surfaces
    the exact validation error inline. `Enter` confirms only when the
    expression validates; an empty value clears the filter.
    """

    DEFAULT_CSS = """
    FilterEditorDialog .field-label {
        padding-top: 1;
    }
    FilterEditorDialog #filter-input {
        margin-bottom: 0;
    }
    FilterEditorDialog #filter-help {
        padding-top: 1;
        color: $text-muted;
    }
    FilterEditorDialog #filter-validation {
        padding-top: 1;
        color: $error;
        text-style: bold;
    }
    FilterEditorDialog #filter-validation.-ok {
        color: $success;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "confirm", "Apply", show=False),
    ]

    confirm_label = "Apply"
    cancel_label = "Cancel"

    def __init__(
        self,
        *,
        title: str = "Advanced filter",
        initial_value: str | None = None,
        validator: Callable[[str | None], FilterValidation],
        help_text: str | None = None,
    ) -> None:
        super().__init__(title=title)
        self._initial_value = initial_value or ""
        self._validator = validator
        self._help_text = (
            help_text
            or "Filter DSL · e.g. status = \"completed\" AND metric.accuracy > 0.85"
        )
        self._last_validation: FilterValidation = FilterValidation(valid=True)

    def compose_body(self) -> Iterable:
        yield Label("Filter expression", classes="field-label")
        yield Input(
            value=self._initial_value,
            placeholder='e.g. tags CONTAINS "prod" AND duration > 60',
            id="filter-input",
        )
        yield Static(self._help_text, id="filter-help")
        yield Static("", id="filter-validation")

    def on_mount(self) -> None:
        super().on_mount()
        try:
            self.query_one("#filter-input", Input).focus()
        except Exception:
            pass
        # Run an initial validation so the user sees state immediately.
        self._run_validation(self._initial_value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "filter-input":
            return
        self._run_validation(event.value)

    def _run_validation(self, value: str) -> None:
        query = value.strip() or None
        try:
            result = self._validator(query)
        except Exception as exc:
            result = FilterValidation(valid=False, error=str(exc))
        self._last_validation = result
        try:
            note = self.query_one("#filter-validation", Static)
        except Exception:
            return
        if query is None:
            # Empty input is always valid (it clears the filter).
            note.update("(empty — clears the filter)")
            note.add_class("-ok")
            return
        if result.valid:
            note.update("✓ valid")
            note.add_class("-ok")
        else:
            note.update(f"✗ {result.error or 'invalid filter expression'}")
            note.remove_class("-ok")

    def action_confirm(self) -> None:
        value = self.query_one("#filter-input", Input).value
        query = value.strip() or None
        if query is not None and not self._last_validation.valid:
            # Block submission until the user fixes the syntax error.
            self.set_error(self._last_validation.error or "Invalid filter expression.")
            return
        self.dismiss(query)

    def action_cancel(self) -> None:
        self.dismiss(None)


_MESSAGE_SEVERITY_STYLES: dict[str, str] = {
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "bold red",
}


class MessageLogDialog(BaseDialog[None]):
    """Rolling log of recent toasts, newest first.

    Toasts are ephemeral; this dialog (palette: "Recent messages") lets
    the user re-read anything they missed — upload errors especially.
    """

    DEFAULT_CSS = """
    MessageLogDialog #message-log-body {
        height: auto;
        max-height: 20;
        border: round $panel;
        padding: 0 1;
    }
    MessageLogDialog .message-log-row {
        height: auto;
    }
    MessageLogDialog #message-log-empty {
        color: $text-muted;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("enter", "confirm", "Close", show=False),
    ]

    confirm_label = "Close"
    cancel_label = "Close"

    def __init__(self, messages: Sequence[tuple[str, str, str]]) -> None:
        super().__init__(title="Recent messages")
        self._messages = list(messages)

    def compose_body(self) -> Iterable:
        with VerticalScroll(id="message-log-body"):
            if not self._messages:
                yield Static("(no messages yet)", id="message-log-empty")
            for timestamp, severity, message in reversed(self._messages):
                style = _MESSAGE_SEVERITY_STYLES.get(severity, "")
                yield Static(
                    Text.assemble(
                        (f"{timestamp}  ", "dim"),
                        (f"{severity:<8}", style),
                        message,
                    ),
                    classes="message-log-row",
                )

    def action_confirm(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
