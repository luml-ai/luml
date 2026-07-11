"""Base screen with breadcrumb/footer plumbing.

The TUI relies on a stack of screens with consistent push/pop. A screen
that is popped back to keeps its selection, scroll position, and active
tab because it stays alive in Textual's stack while children are on top.

The base also owns **panel focus tracking**: every primary region is
wrapped in a ``PanelFrame``, and the frame containing the currently
focused widget renders its border / title in the accent color. The
screen listens for `Focus` events on descendants, walks up to the
enclosing `PanelFrame`, and toggles its `focused` flag so the visible
target moves with `Tab` / `Shift-Tab` (or a direct widget focus).
"""

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from textual.events import DescendantBlur, DescendantFocus
from textual.screen import Screen
from textual.widget import Widget

from lumlflow.tui.keymap import Scope
from lumlflow.tui.widgets import (
    BreadcrumbSegment,
    ContextualFooter,
    PanelFrame,
    StatusHeader,
    ToastHost,
)

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp


class BaseScreen(Screen):
    """Common base for app screens.

    Subclasses override:
    - `breadcrumb_segments` to return the current path
    - `footer_scopes` to declare which keymap scopes apply
    - `focusable_panes` to declare which widgets `Tab` should cycle
    """

    breadcrumb_label: str = ""

    def __init__(
        self,
        *,
        breadcrumb_label: str | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        if breadcrumb_label is not None:
            self.breadcrumb_label = breadcrumb_label
        self._active_panel: PanelFrame | None = None

    def compose(self) -> Iterable[Widget]:
        """Wrap the screen's content in the persistent app chrome.

        The breadcrumb header and contextual footer are docked to the top
        and bottom of *every* screen so navigation context and the key
        hints stay visible no matter how deep the screen stack is. The
        app pushes a fresh screen for each level, so the chrome must live
        on the screen rather than on the app (a pushed screen paints over
        anything mounted on the app's default screen). Subclasses provide
        their body via :meth:`compose_content`.
        """

        yield StatusHeader(id="app-header")
        yield from self.compose_content()
        yield ContextualFooter(
            cast("LumlflowApp", self.app).keymap, id="app-footer"
        )
        yield ToastHost(id="app-toasts")

    def compose_content(self) -> Iterable[Widget]:
        """Yield the screen body (everything between header and footer)."""

        return ()

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        if not self.breadcrumb_label:
            return ()
        return (BreadcrumbSegment(self.breadcrumb_label),)

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global",)

    def focusable_panes(self) -> Iterable[Widget]:
        """Return panes participating in `Tab`/`Shift-Tab` focus cycling.

        Default: an empty iterable means the screen has only one
        focusable area (or none) and the app falls back to its standard
        focus traversal.
        """

        return ()

    # ----- Panel focus tracking -----

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        """Mark the `PanelFrame` enclosing the newly focused widget.

        Walks up the widget tree from the focused descendant until it
        finds a `PanelFrame` (or hits the screen). The previously
        focused frame, if any, is reverted to the muted style.
        """

        frame = self._find_enclosing_panel(event.widget)
        self._set_active_panel(frame)

    def on_descendant_blur(self, _: DescendantBlur) -> None:
        """Best-effort cleanup when focus leaves the screen entirely.

        Textual emits `DescendantFocus` for new focus targets, so the
        active panel will be re-set on the next focus event. We only
        clear here when no widget is currently focused on this screen.
        """

        if self.focused is None:
            self._set_active_panel(None)

    def _find_enclosing_panel(self, widget: Widget) -> PanelFrame | None:
        node: Widget | None = widget
        while node is not None and node is not self:
            if isinstance(node, PanelFrame):
                return node
            parent = node.parent
            if not isinstance(parent, Widget):
                return None
            node = parent
        return None

    def _set_active_panel(self, frame: PanelFrame | None) -> None:
        if frame is self._active_panel:
            return
        if self._active_panel is not None:
            try:
                self._active_panel.set_focused(False)
            except Exception:
                pass
        self._active_panel = frame
        if frame is not None:
            try:
                frame.set_focused(True)
            except Exception:
                pass

    def cycle_focus_pane(self, *, reverse: bool = False) -> bool:
        """Move focus to the next/previous pane declared by the screen.

        Returns ``True`` when focus was moved (i.e. the screen declared
        at least one focusable pane); ``False`` means the caller should
        fall back to Textual's default focus traversal.
        """

        panes = list(self.focusable_panes())
        if not panes:
            return False
        current = self.focused
        try:
            index = panes.index(current) if current in panes else -1
        except ValueError:
            index = -1
        step = -1 if reverse else 1
        if index == -1:
            target = panes[0 if not reverse else -1]
        else:
            target = panes[(index + step) % len(panes)]
        target.focus()
        return True
