"""Reusable bordered, titled panel frame.

Every primary region of the TUI — list tables, detail tab bodies, the
span tree, the span detail, the metric grid, comparison sections — is
wrapped in a `PanelFrame`. The frame draws a rounded border with the
panel title rendered in the top border and an optional right-aligned
subtitle (counts, sort/filter status). When the frame is marked as
``focused`` its border and title switch to the accent color so the user
can see at a glance which pane responds to navigation keys.

The widget is a plain `Container` so children can be composed
declaratively with ``with PanelFrame(...):`` or appended after mount via
``mount``. It does not own the focus of its children; the screen's
``focusable_panes`` (or the children themselves) drive the focus and
the frame mirrors that via the ``focused`` flag.
"""

from __future__ import annotations

from textual.containers import Container
from textual.reactive import reactive


class PanelFrame(Container):
    """Bordered container with a titled top border.

    Set ``title`` to render text in the top border, ``subtitle`` for an
    optional right-aligned subtitle (kept short — counts, filter chips).
    Toggle ``focused`` to swap the border / title between the muted
    ``$panel`` color and the accent color.
    """

    DEFAULT_CSS = """
    PanelFrame {
        height: auto;
        width: 1fr;
        layout: vertical;
        border: round $panel;
        border-title-color: $foreground;
        border-title-background: $surface;
        border-subtitle-color: $foreground;
        border-subtitle-background: $surface;
        padding: 0 1;
        background: $surface;
    }
    PanelFrame.-focused {
        border: round $accent;
        border-title-color: $accent;
        border-title-style: bold;
    }
    PanelFrame.-fill {
        height: 1fr;
    }
    """

    title: reactive[str] = reactive("")
    subtitle: reactive[str] = reactive("")
    focused: reactive[bool] = reactive(False)

    def __init__(
        self,
        *,
        title: str = "",
        subtitle: str = "",
        focused: bool = False,
        fill: bool = False,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._initial_title = title
        self._initial_subtitle = subtitle
        self._initial_focused = focused
        if fill:
            self.add_class("-fill")

    def on_mount(self) -> None:
        # Reactive watchers update the border on subsequent changes, but
        # the very first paint needs an explicit push since reactive
        # initializers don't fire `watch_*` before mount.
        self.title = self._initial_title
        self.subtitle = self._initial_subtitle
        self.focused = self._initial_focused
        self._apply_title()
        self._apply_subtitle()
        self._apply_focus()

    def watch_title(self, _: str) -> None:
        self._apply_title()

    def watch_subtitle(self, _: str) -> None:
        self._apply_subtitle()

    def watch_focused(self, _: bool) -> None:
        self._apply_focus()

    def set_title(self, title: str) -> None:
        self.title = title

    def set_subtitle(self, subtitle: str) -> None:
        self.subtitle = subtitle

    def set_focused(self, focused: bool) -> None:
        self.focused = focused

    def _apply_title(self) -> None:
        self.border_title = self.title or None

    def _apply_subtitle(self) -> None:
        self.border_subtitle = self.subtitle or None

    def _apply_focus(self) -> None:
        if self.focused:
            self.add_class("-focused")
        else:
            self.remove_class("-focused")


__all__ = ["PanelFrame"]
