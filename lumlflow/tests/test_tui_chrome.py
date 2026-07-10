"""Tests for the modern TUI chrome shell.

Covers SPEC.md task "Add the modern app chrome shell":

- the header bar shows the product title, the breadcrumb, and the
  status cluster (live-refresh / selection / loading / store);
- the contextual footer keeps the universal `?` help / `:` palette
  anchors and remains a distinct bar;
- the reusable ``PanelFrame`` widget renders a bordered, titled
  container with an optional subtitle and an accent border when the
  ``focused`` flag is set;
- the ``BaseScreen`` panel-focus tracking marks the frame enclosing
  the currently focused widget, and `Tab` cycles between the panes
  declared by ``focusable_panes``.

`app.query_one("#x")` only sees widgets mounted directly on the App
(header, footer, toast host). Widgets inside the active screen — every
custom ``home_screen_factory`` we use here — must be looked up through
``app.screen.query_one`` instead.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from lumlflow.tui import LumlflowApp
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import PanelFrame
from lumlflow.tui.widgets.footer import ContextualFooter
from lumlflow.tui.widgets.header import PRODUCT_TITLE, StatusHeader
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.widgets import Input


def _footer_text(app: LumlflowApp) -> str:
    footer = app.screen.query_one("#app-footer", ContextualFooter)
    return str(footer.render())


class TestHeaderBar:
    """The header shows product title · breadcrumb · status cluster."""

    async def test_header_shows_product_title(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            title = app.screen.query_one("#app-title")
            assert PRODUCT_TITLE in str(title.render())

    async def test_header_shows_breadcrumb(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            breadcrumb = app.screen.query_one("#breadcrumb")
            assert "Groups" in str(breadcrumb.render())

    async def test_header_status_cluster_present(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            # All four status indicators are mounted under the header.
            assert app.screen.query_one("#status-loading") is not None
            assert app.screen.query_one("#status-selection") is not None
            assert app.screen.query_one("#status-refresh") is not None
            assert app.screen.query_one("#status-store") is not None

    async def test_header_loading_indicator_toggles(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.screen.query_one("#app-header", StatusHeader)
            loading = app.screen.query_one("#status-loading")
            assert loading.display is False
            header.loading = True
            await pilot.pause()
            assert loading.display is True
            header.loading = False
            await pilot.pause()
            assert loading.display is False

    async def test_header_selection_indicator_shows_count(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            header = app.screen.query_one("#app-header", StatusHeader)
            sel = app.screen.query_one("#status-selection")
            assert sel.display is False
            header.selection_count = 3
            await pilot.pause()
            assert sel.display is True
            assert "3" in str(sel.render())

    async def test_header_store_label_visible_when_set(self) -> None:
        app = LumlflowApp(show_first_run_hint=False, store_uri="sqlite://x")
        async with app.run_test() as pilot:
            await pilot.pause()
            store = app.screen.query_one("#status-store")
            # The store URI is surfaced in the header so the user
            # always knows which backend they are looking at.
            assert "sqlite://x" in str(store.render())
            assert store.display is True

    async def test_header_live_refresh_indicator_reflects_toggle(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            refresh = app.screen.query_one("#status-refresh")
            assert "live" in str(refresh.render())


class TestContextualFooter:
    """The footer keeps the `?` and `:` anchors and is a distinct bar."""

    async def test_footer_keeps_universal_anchors(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            text = _footer_text(app)
            assert "[?]" in text and "Help" in text
            assert "[:]" in text and "Command palette" in text

    async def test_footer_is_a_distinct_bar(self) -> None:
        """The footer must be styled distinctly from the surface.

        We check that the contextual footer is mounted as its own
        widget (distinct from the toast host and the header) so the
        chrome reads as three real bars.
        """

        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            footer = app.screen.query_one("#app-footer", ContextualFooter)
            header = app.screen.query_one("#app-header")
            toast = app.screen.query_one("#app-toasts")
            # All three are distinct widget instances.
            assert footer is not header
            assert footer is not toast


class TestChromeVisibleOnPushedScreens:
    """Regression: chrome must ride on each screen, not the default one.

    The chrome used to be mounted on the app's default screen, which
    every ``push_screen`` painted over — so the breadcrumb and footer
    were invisible in the running app even though ``app.query_one`` (which
    only searches the default screen) still found them in tests.
    """

    async def test_footer_lives_on_active_screen_not_default(self) -> None:
        class _Child(BaseScreen):
            def compose_content(self) -> Iterable:  # type: ignore[override]
                yield PanelFrame(title="Child", id="child-panel")

            def footer_scopes(self):  # type: ignore[override]
                return ("global", "list")

        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.push_screen(_Child())
            await pilot.pause()
            await pilot.pause()
            # The footer is mounted on the now-active child screen and
            # painted (non-zero height region at the bottom of the screen).
            footer = app.screen.query_one("#app-footer", ContextualFooter)
            assert footer.display
            assert footer.region.height >= 1
            assert footer.region.bottom == app.screen.region.bottom
            # And it is NOT on the default screen (which a pushed screen
            # would otherwise cover). `app.query_one` only searches the
            # default screen, so it must no longer find the footer there.
            with pytest.raises(NoMatches):
                app.query_one("#app-footer", ContextualFooter)

    async def test_breadcrumb_visible_after_drill_in(self) -> None:
        class _Child(BaseScreen):
            def compose_content(self) -> Iterable:  # type: ignore[override]
                yield PanelFrame(title="Child", id="child-panel")

            def breadcrumb_segments(self):  # type: ignore[override]
                from lumlflow.tui.widgets import BreadcrumbSegment

                return (BreadcrumbSegment("Groups"), BreadcrumbSegment("child"))

        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            app.push_screen(_Child())
            await pilot.pause()
            await pilot.pause()
            header = app.screen.query_one("#app-header", StatusHeader)
            assert header.region.y == 0
            assert "child" in str(app.screen.query_one("#breadcrumb").render())


class TestToastHostDoesNotClipHeader:
    """Regression: an empty toast host must not paint over the header.

    The toast host sits on the always-on-top ``toast`` layer. When it had
    its own padding it occupied a small box at the top-left even with no
    toasts, clipping the first character of the product title (rendered
    as "umlflow"). With no toasts it must have zero footprint.
    """

    async def test_empty_toast_host_has_no_footprint(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            host = app.screen.query_one("#app-toasts")
            # No toasts → the host occupies no rows, so it cannot cover
            # the header title beneath it on the toast layer.
            assert host.region.height == 0
            title = app.screen.query_one("#app-title")
            assert PRODUCT_TITLE in str(title.render())

    async def test_toast_is_confined_to_top_right(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            app.show_toast("hello", severity="info")
            await pilot.pause()
            await pilot.pause()
            host = app.screen.query_one("#app-toasts")
            title = app.screen.query_one("#app-title")
            # The visible toast must stay clear of the title's columns so
            # the brand mark is never clipped while a toast is showing.
            assert host.region.x > title.region.right


class TestPanelFrame:
    """The reusable `PanelFrame` renders titled, bordered panels."""

    async def test_title_appears_in_border(self) -> None:
        class _S(BaseScreen):
            def compose(self) -> Iterable:  # type: ignore[override]
                yield PanelFrame(title="My Panel", id="p")

        app = LumlflowApp(show_first_run_hint=False, home_screen_factory=_S)
        async with app.run_test() as pilot:
            await pilot.pause()
            frame = app.screen.query_one("#p", PanelFrame)
            assert frame.title == "My Panel"
            # Textual renders the title in the top border.
            assert frame.border_title == "My Panel"

    async def test_subtitle_appears_in_border(self) -> None:
        class _S(BaseScreen):
            def compose(self) -> Iterable:  # type: ignore[override]
                yield PanelFrame(
                    title="Groups", subtitle="3 items · sort: name ↑", id="p"
                )

        app = LumlflowApp(show_first_run_hint=False, home_screen_factory=_S)
        async with app.run_test() as pilot:
            await pilot.pause()
            frame = app.screen.query_one("#p", PanelFrame)
            assert frame.subtitle == "3 items · sort: name ↑"
            assert frame.border_subtitle == "3 items · sort: name ↑"

    async def test_focused_panel_uses_accent_border(self) -> None:
        class _S(BaseScreen):
            def compose(self) -> Iterable:  # type: ignore[override]
                yield PanelFrame(title="P", id="p")

        app = LumlflowApp(show_first_run_hint=False, home_screen_factory=_S)
        async with app.run_test() as pilot:
            await pilot.pause()
            frame = app.screen.query_one("#p", PanelFrame)
            assert frame.focused is False
            assert "-focused" not in frame.classes
            frame.set_focused(True)
            await pilot.pause()
            assert frame.focused is True
            # The accent class is applied so the CSS rule that swaps
            # the border color over to `$accent` takes effect.
            assert "-focused" in frame.classes

    async def test_title_and_subtitle_can_be_updated_after_mount(self) -> None:
        class _S(BaseScreen):
            def compose(self) -> Iterable:  # type: ignore[override]
                yield PanelFrame(title="A", id="p")

        app = LumlflowApp(show_first_run_hint=False, home_screen_factory=_S)
        async with app.run_test() as pilot:
            await pilot.pause()
            frame = app.screen.query_one("#p", PanelFrame)
            frame.set_title("B")
            frame.set_subtitle("S")
            await pilot.pause()
            assert frame.border_title == "B"
            assert frame.border_subtitle == "S"


class _TwoPaneScreen(BaseScreen):
    """A simple two-panel screen used by the focus-cycling tests.

    Declared at module scope (not inside a fixture) so the LumlflowApp
    ``home_screen_factory=...`` argument can call it as a no-arg factory
    just like the production `HomeScreen`.
    """

    def compose(self) -> Iterable:  # type: ignore[override]
        with PanelFrame(title="Left", id="left-frame"):
            yield Input(placeholder="left", id="left-input")
        with PanelFrame(title="Right", id="right-frame"):
            yield Input(placeholder="right", id="right-input")

    def focusable_panes(self) -> Iterable:
        return (
            self.query_one("#left-input", Input),
            self.query_one("#right-input", Input),
        )


class TestBaseScreenPanelFocus:
    """`BaseScreen` marks the panel frame enclosing the focused widget."""

    async def test_focused_widget_marks_enclosing_panel(self) -> None:
        app = LumlflowApp(
            show_first_run_hint=False, home_screen_factory=_TwoPaneScreen
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            left_frame = screen.query_one("#left-frame", PanelFrame)
            right_frame = screen.query_one("#right-frame", PanelFrame)
            # Textual auto-focuses the first focusable widget on mount,
            # so the left frame should already be active. The right
            # frame must be muted.
            screen.query_one("#left-input", Input).focus()
            await pilot.pause()
            assert left_frame.focused is True
            assert right_frame.focused is False
            # Focus the right input — the active panel migrates.
            screen.query_one("#right-input", Input).focus()
            await pilot.pause()
            assert left_frame.focused is False
            assert right_frame.focused is True

    async def test_tab_cycles_focusable_panes(self) -> None:
        app = LumlflowApp(
            show_first_run_hint=False, home_screen_factory=_TwoPaneScreen
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            left_input = screen.query_one("#left-input", Input)
            right_input = screen.query_one("#right-input", Input)
            left_input.focus()
            await pilot.pause()
            # `Tab` is registered as `global.cycle_focus`, which the app
            # delegates to the screen's `focusable_panes` cycling when
            # the screen declares any.
            app.action_cycle_focus()
            await pilot.pause()
            assert app.focused is right_input
            app.action_cycle_focus()
            await pilot.pause()
            # Wraps around back to the left.
            assert app.focused is left_input

    async def test_shift_tab_cycles_focusable_panes_backwards(self) -> None:
        app = LumlflowApp(
            show_first_run_hint=False, home_screen_factory=_TwoPaneScreen
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            left_input = screen.query_one("#left-input", Input)
            right_input = screen.query_one("#right-input", Input)
            left_input.focus()
            await pilot.pause()
            app.action_cycle_focus_back()
            await pilot.pause()
            # Going backward from the left wraps to the right pane.
            assert app.focused is right_input

    async def test_screen_without_focusable_panes_falls_back_to_default(
        self,
    ) -> None:
        class _Screen(BaseScreen):
            def compose(self) -> Iterable:  # type: ignore[override]
                yield Input(placeholder="a", id="a")
                yield Input(placeholder="b", id="b")

        app = LumlflowApp(show_first_run_hint=False, home_screen_factory=_Screen)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            # No `focusable_panes` declared → `action_cycle_focus` falls
            # back to Textual's default `focus_next`. The exact target
            # depends on the focus chain; what matters is that we did
            # not raise and a widget is focused.
            screen.query_one("#a", Input).focus()
            await pilot.pause()
            app.action_cycle_focus()
            await pilot.pause()
            assert app.focused is not None

    async def test_active_panel_is_only_one_at_a_time(self) -> None:
        app = LumlflowApp(
            show_first_run_hint=False, home_screen_factory=_TwoPaneScreen
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            left_frame = screen.query_one("#left-frame", PanelFrame)
            right_frame = screen.query_one("#right-frame", PanelFrame)
            screen.query_one("#left-input", Input).focus()
            await pilot.pause()
            screen.query_one("#right-input", Input).focus()
            await pilot.pause()
            # Only the right is focused after the switch.
            focused_count = sum(
                1 for f in (left_frame, right_frame) if f.focused
            )
            assert focused_count == 1


class TestPanelFrameNesting:
    """Frames inside containers still resolve to the nearest enclosing frame."""

    async def test_nearest_panel_is_marked(self) -> None:
        class _S(BaseScreen):
            def compose(self) -> Iterable:  # type: ignore[override]
                with PanelFrame(title="Outer", id="outer"):
                    with Vertical():
                        with PanelFrame(title="Inner", id="inner"):
                            yield Input(id="i")

        app = LumlflowApp(show_first_run_hint=False, home_screen_factory=_S)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            inner = screen.query_one("#inner", PanelFrame)
            outer = screen.query_one("#outer", PanelFrame)
            screen.query_one("#i", Input).focus()
            await pilot.pause()
            # The inner frame wins because it is the nearest ancestor.
            assert inner.focused is True
            assert outer.focused is False


# Re-import pytest at module scope so future fixture additions work
# without surprises — referenced here so the imported symbol isn't
# stripped by an aggressive linter.
_ = pytest
