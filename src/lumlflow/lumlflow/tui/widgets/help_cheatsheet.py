"""Searchable help cheat-sheet modal.

Renders every command in the keymap registry, grouped by `Command.group`
with its key binding(s). The dialog supports incremental filtering: as
the user types into the search input, rows whose label, description, or
key text contain the query are kept and others hidden.

The cheat-sheet is the *full grouped view* of the no-hidden-shortcuts
invariant — it is the user-facing dual of the central keymap registry.
The footer shows what's relevant right now, the command palette is the
fuzzy "find any action by name" surface, and this is the "show me
everything I can do" reference.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable

from rich.text import Text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Input, Static

from lumlflow.tui.keymap import Command, KeymapRegistry, Scope
from lumlflow.tui.widgets.footer import display_key
from lumlflow.tui.widgets.modal import BaseDialog

# Group label for the lead section listing the active screen's commands.
_HERE_GROUP = "Available here"


def _format_keys(cmd: Command) -> Text:
    keys = Text()
    for i, key in enumerate(cmd.display_keys):
        if i > 0:
            keys.append(" / ", style="dim")
        keys.append(f"[{display_key(key)}]", style="bold cyan")
    return keys


def _format_row(cmd: Command) -> Text:
    row = Text()
    keys = _format_keys(cmd)
    row.append_text(keys)
    row.append(" ")
    row.append(cmd.label, style="bold")
    row.append("  ")
    row.append(cmd.description, style="dim")
    return row


def _row_match_text(cmd: Command) -> str:
    """Plain text used for incremental search matching."""

    keys = " ".join(display_key(k) for k in cmd.display_keys)
    return f"{cmd.label} {cmd.description} {keys} {cmd.group} {cmd.id}".lower()


class HelpCheatsheet(BaseDialog[None]):
    """Modal cheat-sheet derived from the keymap registry."""

    DEFAULT_CSS = """
    HelpCheatsheet > Vertical {
        width: 90;
        max-width: 95%;
        height: 80%;
        min-height: 20;
    }
    HelpCheatsheet #help-search {
        margin-bottom: 1;
    }
    HelpCheatsheet #help-body {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
        background: $surface;
    }
    HelpCheatsheet .help-group-label {
        text-style: bold;
        color: $accent;
        padding: 1 0 0 0;
    }
    HelpCheatsheet .help-row {
        height: 1;
        padding: 0 1;
    }
    HelpCheatsheet .help-row.-hidden {
        display: none;
    }
    HelpCheatsheet .help-group-label.-hidden {
        display: none;
    }
    HelpCheatsheet #help-empty {
        padding: 2 4;
        color: $text-muted;
    }
    HelpCheatsheet #help-empty.-hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("enter", "cancel", "Close", show=False),
    ]

    confirm_label = "Close"
    cancel_label = "Close"

    def __init__(
        self,
        registry: KeymapRegistry,
        *,
        active_scopes: tuple[Scope, ...] = (),
    ) -> None:
        super().__init__(title="Help · Keymap")
        self._registry = registry
        self._active_scopes = active_scopes
        self._row_widgets: list[tuple[Command, Static]] = []
        self._group_widgets: dict[str, Static] = {}

    def compose_body(self) -> Iterable:
        yield Input(
            placeholder="Search bindings (name, description, or key)",
            id="help-search",
        )
        with VerticalScroll(id="help-body"):
            yield Static("No commands match the search.", id="help-empty")
            for group_label, commands in self._grouped_commands().items():
                group_widget = Static(group_label, classes="help-group-label")
                self._group_widgets[group_label] = group_widget
                yield group_widget
                for cmd in commands:
                    row = Static(_format_row(cmd), classes="help-row")
                    self._row_widgets.append((cmd, row))
                    yield row

    def _grouped_commands(self) -> OrderedDict[str, list[Command]]:
        """Group commands by their `group` field, preserving insertion order.

        When the caller passed the active screen's scopes, a lead
        "Available here" section lists the contextual (non-global)
        commands that work right now — the direct answer to "what can
        I press on this screen". The same commands still appear in
        their canonical groups below.
        """

        groups: OrderedDict[str, list[Command]] = OrderedDict()
        contextual = [
            cmd
            for cmd in self._registry.all()
            if cmd.scope in self._active_scopes
            and cmd.scope != "global"
            and not cmd.palette_only
        ]
        if contextual:
            groups[_HERE_GROUP] = contextual
        for cmd in self._registry.all():
            groups.setdefault(cmd.group, []).append(cmd)
        return groups

    def on_mount(self) -> None:
        super().on_mount()
        try:
            search = self.query_one("#help-search", Input)
            search.focus()
        except Exception:
            pass
        self._update_visibility("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "help-search":
            return
        self._update_visibility(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter on the search input simply closes the dialog (so the
        # control rule "Enter confirms" is preserved).
        if event.input.id == "help-search":
            self.dismiss(None)

    def _update_visibility(self, query: str) -> None:
        needle = query.strip().lower()
        any_match = False
        visible_groups: set[str] = set()
        for cmd, row in self._row_widgets:
            haystack = _row_match_text(cmd)
            if not needle or needle in haystack:
                row.remove_class("-hidden")
                visible_groups.add(cmd.group)
                any_match = True
            else:
                row.add_class("-hidden")
        for label, widget in self._group_widgets.items():
            if label in visible_groups:
                widget.remove_class("-hidden")
            else:
                widget.add_class("-hidden")
        try:
            empty = self.query_one("#help-empty", Static)
            if any_match:
                empty.add_class("-hidden")
            else:
                empty.remove_class("-hidden")
        except Exception:
            pass

    def action_confirm(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


__all__ = ["HelpCheatsheet"]
