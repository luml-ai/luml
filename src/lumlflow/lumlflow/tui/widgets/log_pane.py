"""Scrollable log pane for the run-and-attach mode.

The pane streams the child process's stdout/stderr line-by-line and
surfaces the exit code on completion. stdout lines render in the
foreground color; stderr lines render in the warning color so failures
stand out at a glance.

Implemented on top of `RichLog` (Textual's built-in scrollable log
widget) so the user has the full keyboard scroll-and-search affordances
without us reinventing them.
"""

from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.widgets import RichLog


class RunLogPane(RichLog):
    """A `RichLog`-backed pane that styles lines by stream."""

    DEFAULT_CSS = """
    RunLogPane {
        height: 1fr;
        border: round $panel;
        padding: 0 1;
        background: $surface;
    }
    """

    BINDINGS = [
        # The log pane is purely passive; we surface a couple of obvious
        # scroll keys so they have an explicit affordance and don't get
        # swallowed by global bindings when the pane has focus.
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G", "scroll_end", "Bottom", show=False),
    ]

    def __init__(
        self,
        *,
        id: str | None = None,
    ) -> None:
        # `auto_scroll=True` keeps the latest line visible as the script
        # writes; `wrap=True` so long log lines wrap rather than scroll
        # horizontally (terminals get narrow; reading wrapped text wins).
        super().__init__(
            id=id,
            auto_scroll=True,
            wrap=True,
            markup=False,
            highlight=False,
        )

    # ----- writes -----

    def append_line(self, stream: str, line: str) -> None:
        """Append one line, coloured by stream.

        `stream` is "stdout" or "stderr" — anything else is treated as
        an info line (used for status messages like "process exited").
        """

        style = "dim" if stream == "stdout" else "yellow"
        if stream not in {"stdout", "stderr"}:
            style = "cyan"
        text = Text(line, style=style)
        self.write(text)

    def append_status(self, message: str, *, level: str = "info") -> None:
        """Append a TUI-generated status line (process started/exited)."""

        color = {
            "info": "cyan",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        }.get(level, "cyan")
        text = Text(message, style=f"bold {color}")
        self.write(text)


__all__ = ("RunLogPane",)
