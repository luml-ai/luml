"""Fuzzy command palette modal.

The palette is dual-purpose per SPEC.md:

- **jump-to**: any screen, or a group/experiment by name
- **run-action**: every registered command, with its binding shown

Both halves are searchable by a single query. The query matches against
the entry's label and any indexing hints (description, group, key
strings). Matching is forgiving — characters of the query just have to
appear in the haystack in order (subsequence fuzzy match) — and entries
are ranked by how tight the match is, so the most likely match floats
to the top.

This modal is also where SPEC parks the **select-all** / **clear
selection** commands ("Select-all / clear are available via the
palette"). Those commands are registered as palette-only entries on the
keymap registry so they show up here and in `?`, but never claim a
key binding that could collide with a list-scope verb.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, ListItem, ListView, Static

from lumlflow.tui.keymap import Command, KeymapRegistry
from lumlflow.tui.widgets.footer import display_key
from lumlflow.tui.widgets.modal import BaseDialog

# Kinds of entries the palette can carry. Distinguishing them in the
# render lets us colour the prefix and helps tests assert on the right
# entry without inspecting the underlying action.
EntryKind = str  # "command" | "screen" | "group" | "experiment"


@dataclass(frozen=True)
class PaletteEntry:
    """One row shown in the palette.

    The `invoke` callback fires on Enter; it does its own work (push a
    screen, fire a command action, etc.) and the palette dismisses
    itself.
    """

    label: str
    description: str
    kind: EntryKind
    invoke: Callable[[], None]
    keys: tuple[str, ...] = ()
    extra_search: str = ""

    def haystack(self) -> str:
        return (
            f"{self.label} {self.description} {self.kind} "
            f"{self.extra_search} {' '.join(self.keys)}"
        ).lower()


def fuzzy_score(query: str, haystack: str) -> int | None:
    """Score how well `query` matches `haystack` as an ordered subsequence.

    Returns `None` if the query characters don't appear in order. A
    lower score is a better match: zero is a perfect prefix match, and
    bigger numbers correspond to looser matches (more gaps between
    characters). This is intentionally simple — it captures the spirit
    of fuzzy matching ("typed letters appear in order") without
    pulling in a dependency.
    """

    if not query:
        return 0
    haystack_l = haystack.lower()
    needle = query.lower()
    cursor = 0
    score = 0
    gap = 0
    last_index: int | None = None
    for ch in needle:
        idx = haystack_l.find(ch, cursor)
        if idx == -1:
            return None
        # Penalise distance from the last matched character so adjacent
        # matches sort above scattered ones.
        if last_index is not None:
            gap += idx - last_index - 1
        else:
            # Penalise distance from the start of the haystack so
            # earlier matches sort above later ones.
            score += idx
        last_index = idx
        cursor = idx + 1
    return score + gap


def _format_entry(entry: PaletteEntry) -> Text:
    """Render a palette row: kind chip · label · keys · description."""

    text = Text()
    kind_colors = {
        "command": "yellow",
        "screen": "cyan",
        "group": "green",
        "experiment": "magenta",
        "action": "yellow",
    }
    color = kind_colors.get(entry.kind, "white")
    text.append(f"{entry.kind:11}", style=f"bold {color}")
    text.append("  ")
    text.append(entry.label, style="bold")
    if entry.keys:
        text.append("  ")
        for i, key in enumerate(entry.keys):
            if i > 0:
                text.append(" / ", style="dim")
            text.append(f"[{display_key(key)}]", style="bold cyan")
    if entry.description:
        text.append("  ")
        text.append(entry.description, style="dim")
    return text


def entries_for_registry(
    registry: KeymapRegistry,
    *,
    runner: Callable[[Command], None],
    exclude_ids: Iterable[str] = (),
) -> list[PaletteEntry]:
    """Build palette entries for every registered command.

    `runner` is invoked with the chosen `Command` so the host app can
    route to the same action methods as the bindings.
    """

    excluded = set(exclude_ids)
    rows: list[PaletteEntry] = []

    def _make_invoke(cmd: Command) -> Callable[[], None]:
        # Pin `cmd` via a closure so each entry invokes its own command
        # — a plain `lambda` over the loop variable would all bind to
        # the last command.
        def _invoke() -> None:
            runner(cmd)

        return _invoke

    for cmd in registry.all():
        if cmd.id in excluded:
            continue
        rows.append(
            PaletteEntry(
                label=cmd.label,
                description=cmd.description,
                kind="command",
                invoke=_make_invoke(cmd),
                keys=cmd.display_keys,
                extra_search=f"{cmd.group} {cmd.id}",
            )
        )
    return rows


class CommandPalette(BaseDialog[None]):
    """Fuzzy palette modal showing every action + every jump-to target."""

    DEFAULT_CSS = """
    CommandPalette > Vertical {
        width: 100;
        max-width: 95%;
        height: 80%;
        min-height: 18;
    }
    CommandPalette #palette-search {
        margin-bottom: 1;
    }
    CommandPalette #palette-results {
        height: 1fr;
        border: round $primary;
        background: $surface;
    }
    CommandPalette ListView > ListItem {
        padding: 0 1;
    }
    CommandPalette ListView > ListItem.--highlight {
        background: $accent 30%;
    }
    CommandPalette #palette-empty {
        padding: 2 4;
        color: $text-muted;
        display: none;
    }
    CommandPalette #palette-empty.-visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("enter", "confirm", "Run", show=False),
        Binding("down", "list_down", "Down", show=False),
        Binding("up", "list_up", "Up", show=False),
        Binding("ctrl+n", "list_down", "Down", show=False),
        Binding("ctrl+p", "list_up", "Up", show=False),
    ]

    confirm_label = "Run"
    cancel_label = "Close"

    # Limit results to avoid rendering thousands of entity rows.
    MAX_RESULTS = 200

    def __init__(
        self,
        *,
        registry: KeymapRegistry,
        command_runner: Callable[[Command], None],
        extra_entries: Sequence[PaletteEntry] = (),
        exclude_command_ids: Iterable[str] = (),
        placeholder: str = "Type to search · jump to · run action",
    ) -> None:
        super().__init__(title="Command palette")
        self._registry = registry
        self._command_runner = command_runner
        self._extra_entries = list(extra_entries)
        self._exclude = set(exclude_command_ids)
        self._placeholder = placeholder
        self._all_entries: list[PaletteEntry] = []
        self._visible_entries: list[PaletteEntry] = []

    def compose_body(self) -> Iterable:
        yield Input(placeholder=self._placeholder, id="palette-search")
        with Vertical(id="palette-results"):
            yield ListView(id="palette-list")
            yield Static("No matches.", id="palette-empty")

    def on_mount(self) -> None:
        super().on_mount()
        self._all_entries = self._build_entries()
        self._apply_query("")
        try:
            self.query_one("#palette-search", Input).focus()
        except Exception:
            pass

    def _build_entries(self) -> list[PaletteEntry]:
        rows: list[PaletteEntry] = list(self._extra_entries)
        rows.extend(
            entries_for_registry(
                self._registry,
                runner=self._command_runner,
                exclude_ids=self._exclude,
            )
        )
        return rows

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "palette-search":
            return
        self._apply_query(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Submitting the input is equivalent to Enter on the highlighted row.
        if event.input.id == "palette-search":
            self.action_confirm()

    def _apply_query(self, raw_query: str) -> None:
        query = raw_query.strip()
        scored: list[tuple[int, int, PaletteEntry]] = []
        for i, entry in enumerate(self._all_entries):
            score = fuzzy_score(query, entry.haystack())
            if score is None:
                continue
            scored.append((score, i, entry))
        scored.sort(key=lambda triple: (triple[0], triple[1]))
        results = [entry for (_, _, entry) in scored[: self.MAX_RESULTS]]
        self._visible_entries = results
        try:
            listview = self.query_one("#palette-list", ListView)
        except Exception:
            return
        listview.clear()
        for entry in results:
            listview.append(ListItem(Static(_format_entry(entry))))
        try:
            empty = self.query_one("#palette-empty", Static)
        except Exception:
            empty = None  # type: ignore[assignment]
        if empty is not None:
            if results:
                empty.remove_class("-visible")
                listview.display = True
            else:
                empty.add_class("-visible")
                listview.display = False
        if results:
            listview.index = 0

    def action_list_down(self) -> None:
        try:
            listview = self.query_one("#palette-list", ListView)
        except Exception:
            return
        if not self._visible_entries:
            return
        current = listview.index or 0
        listview.index = min(current + 1, len(self._visible_entries) - 1)

    def action_list_up(self) -> None:
        try:
            listview = self.query_one("#palette-list", ListView)
        except Exception:
            return
        if not self._visible_entries:
            return
        current = listview.index or 0
        listview.index = max(current - 1, 0)

    def action_confirm(self) -> None:
        if not self._visible_entries:
            self.dismiss(None)
            return
        try:
            listview = self.query_one("#palette-list", ListView)
            idx = listview.index or 0
        except Exception:
            idx = 0
        idx = max(0, min(idx, len(self._visible_entries) - 1))
        entry = self._visible_entries[idx]
        # Dismiss first so the underlying screen is on top when the
        # entry's invoke pushes a new screen / fires a global action.
        self.dismiss(None)
        try:
            entry.invoke()
        except Exception as exc:  # pragma: no cover - defensive
            app = self.app
            try:
                app.show_toast(f"Could not run: {exc}", severity="error")  # type: ignore[attr-defined]
            except Exception:
                pass

    def action_cancel(self) -> None:
        self.dismiss(None)


__all__: tuple[str, ...] = (
    "CommandPalette",
    "PaletteEntry",
    "entries_for_registry",
    "fuzzy_score",
)
