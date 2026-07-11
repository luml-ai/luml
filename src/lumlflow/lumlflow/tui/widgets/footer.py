"""Contextual footer derived from the keymap registry.

A distinct, contextual bar at the bottom of the app, anchored by the
universal ``?`` help · ``:`` commands hints so the user can reach the
cheat-sheet and palette from anywhere. The footer pulls its visible
hints from the keymap registry's ``footer_for`` query against the
active screen's scopes — so any newly registered command surfaces here
automatically.

The bar is styled distinctly (panel background, single-cell tall, with
top/bottom padding zero) rather than blending into the surface so the
chrome reads as a real footer and not a stray status line.
"""

from collections.abc import Iterable

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from lumlflow.tui.keymap import Command, KeymapRegistry, Scope

_KEY_LABELS: dict[str, str] = {
    "question_mark": "?",
    "colon": ":",
    "escape": "Esc",
    "enter": "Enter",
    "tab": "Tab",
    "shift+tab": "S-Tab",
    "ctrl+p": "C-p",
    "ctrl+c": "C-c",
    "ctrl+d": "C-d",
    "ctrl+u": "C-u",
    "pagedown": "PgDn",
    "pageup": "PgUp",
    "down": "↓",
    "up": "↑",
    "left": "←",
    "right": "→",
    "space": "Space",
}


def display_key(key: str) -> str:
    return _KEY_LABELS.get(key, key)


class ContextualFooter(Static):
    """Footer that mirrors the keymap registry for the current scopes."""

    DEFAULT_CSS = """
    ContextualFooter {
        dock: bottom;
        /* The top border draws the accent divider; the content rows
         * carry the hint text. Height is auto so the hints wrap onto a
         * second (or third) row on narrow terminals instead of being
         * ellipsised away — every hint stays visible at any width. The
         * cap keeps a pathologically narrow terminal from letting the
         * footer eat the screen. */
        height: auto;
        max-height: 4;
        padding: 0 1;
        background: $panel;
        color: $foreground;
        border-top: hkey $primary-darken-1;
    }
    """

    scopes: reactive[tuple[Scope, ...]] = reactive(("global",))

    def __init__(
        self,
        registry: KeymapRegistry,
        *,
        scopes: tuple[Scope, ...] = ("global",),
        id: str | None = None,
    ) -> None:
        super().__init__("", id=id)
        self._registry = registry
        self.scopes = scopes

    def set_scopes(self, scopes: Iterable[Scope]) -> None:
        self.scopes = tuple(scopes)

    def watch_scopes(self, _: tuple[Scope, ...]) -> None:
        self._render_hints()

    def on_mount(self) -> None:
        self._render_hints()

    def _render_hints(self) -> None:
        commands = self._registry.footer_for(self.scopes)
        # The two universal anchors lead the bar — they are the entry
        # points to everything else (`?` opens the full cheat-sheet,
        # `:` the palette). The text wraps rather than truncates so no
        # hint disappears on a narrow terminal.
        help_cmd = self._registry.get("global.help")
        palette_cmd = self._registry.get("global.palette")
        text = Text()
        self._append_command(text, help_cmd)
        text.append("  ")
        self._append_command(text, palette_cmd)
        exclude_ids = {help_cmd.id, palette_cmd.id}
        unique = self._iter_unique(commands, exclude=exclude_ids)
        if unique:
            text.append("   │   ", style="dim")
        for i, cmd in enumerate(unique):
            if i > 0:
                text.append("  ", style="dim")
            self._append_command(text, cmd)
        self.update(text)

    @staticmethod
    def _iter_unique(
        commands: Iterable[Command],
        *,
        exclude: set[str],
    ) -> list[Command]:
        seen: set[str] = set()
        result: list[Command] = []
        for cmd in commands:
            if cmd.id in exclude or cmd.id in seen:
                continue
            seen.add(cmd.id)
            result.append(cmd)
        return result

    @staticmethod
    def _append_command(text: Text, cmd: Command) -> None:
        # Rich's style parser does not expand Textual's `$accent` token,
        # so we use a literal bold color that reads well on both the
        # dark and light themes (similar contrast to the accent blue).
        # The no-break space keeps `[key] Label` atomic when the footer
        # wraps on a narrow terminal.
        text.append(f"[{display_key(cmd.key)}]", style="bold cyan")
        text.append(f" {cmd.label}")
