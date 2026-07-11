"""Tests for the TUI app shell.

The contract covered here mirrors the first task in SPEC.md:
- the app boots to the home screen,
- the contextual footer reflects the keymap registry, and
- the modeless-input rule holds (letters typed inside a text input are
  literal, not command shortcuts).
"""

import pytest
from lumlflow.tui import LumlflowApp, build_default_registry
from lumlflow.tui.keymap import KeymapRegistry
from lumlflow.tui.screens.home import HomeScreen
from textual.widgets import Input


def _footer_text(app: LumlflowApp) -> str:
    footer = app.screen.query_one("#app-footer")
    rendered = footer.render()
    return str(rendered)


async def test_footer_reserves_a_visible_content_row() -> None:
    """The footer must have room to render its hints, not just a border.

    Regression: the footer was `height: 1` with a `border-top`, so the
    border consumed the only row and the hint text rendered into zero
    content height — the bar looked empty on every screen.
    """

    app = LumlflowApp(show_first_run_hint=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.screen.query_one("#app-footer")
        # `size` is the content box (border excluded): it must be at
        # least one row so the hints are actually painted.
        assert footer.size.height >= 1
        assert _footer_text(app).strip() != ""


async def test_app_boots_to_home_screen() -> None:
    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        # Theme defaults to dark.
        assert app.theme == "luml-dark"
        # Header + footer + toast host are mounted.
        assert app.screen.query_one("#app-header") is not None
        assert app.screen.query_one("#app-footer") is not None
        assert app.screen.query_one("#app-toasts") is not None


async def test_footer_reflects_registry() -> None:
    """The footer derives its hints from the keymap registry.

    Every command registered as a global shortcut with `show_in_footer`
    must appear in the rendered footer text, alongside the universal
    `?` help and `:` palette anchors.
    """

    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        text = _footer_text(app)
        # The two universal anchors are always present at the end.
        assert "[?]" in text
        assert "Help" in text
        assert "[:]" in text
        assert "Command palette" in text
        # Other global commands surface in the footer:
        assert "Refresh" in text
        assert "Back" in text
        assert "Upload" in text
        # Rare toggles stay off the footer (still in `?` / the palette)
        # so the hint bar fits without truncation on narrow terminals.
        assert "Auto-refresh" not in text
        assert "Theme" not in text


async def test_footer_includes_scope_commands_for_list_screens() -> None:
    """A list-scope screen should surface list-scope commands too."""

    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # HomeScreen declares both `global` and `list` scopes.
        text = _footer_text(app)
        for label in ("Open", "Search", "Filter", "Sort", "Edit", "Delete"):
            assert label in text, f"{label!r} missing from footer: {text!r}"


async def test_modeless_input_letters_are_literal() -> None:
    """Letters typed in a search input must be literal, not commands.

    SPEC scenario "Modeless input rule": pressing `/` then typing
    `d`, `e`, `s` enters those letters as search text (not delete /
    edit / sort commands).
    """

    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # `/` opens the incremental search input on a list screen.
        await pilot.press("slash")
        await pilot.pause()
        search = app.screen.query_one("#groups-search", Input)
        assert app.focused is search
        await pilot.press("d")
        await pilot.press("e")
        await pilot.press("t")
        await pilot.press("s")
        await pilot.pause()
        assert search.value == "dets", search.value


async def test_modeless_input_esc_still_acts_as_control() -> None:
    """Inside an input, Esc must still act as a control (blur)."""

    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("slash")
        await pilot.pause()
        search = app.screen.query_one("#groups-search", Input)
        assert app.focused is search
        await pilot.press("escape")
        await pilot.pause()
        # After Esc, focus should not be on the input any more.
        assert app.focused is not search


async def test_outside_input_letters_invoke_commands() -> None:
    """The other side of the modeless rule.

    When no input has focus, pressing `R` toggles auto-refresh — a
    registered global single-letter action.
    """

    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Make sure focus is not on a text input.
        if app.focused is not None and isinstance(app.focused, Input):
            app.focused.blur()
            await pilot.pause()
        assert app.live_refresh_on is True
        await pilot.press("R")
        await pilot.pause()
        assert app.live_refresh_on is False


async def test_breadcrumb_reflects_active_screen() -> None:
    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        breadcrumb = app.screen.query_one("#breadcrumb")
        rendered = str(breadcrumb.render())
        assert "Groups" in rendered


async def test_custom_keymap_is_used() -> None:
    """The app must take any registry passed in and drive the footer from it."""

    custom = build_default_registry()
    app = LumlflowApp(keymap=custom)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.keymap is custom


async def test_registry_disallows_duplicate_ids() -> None:
    from lumlflow.tui.keymap import Command

    registry = KeymapRegistry()
    registry.register(Command(id="x", key="x", label="X", description="."))
    with pytest.raises(ValueError):
        registry.register(Command(id="x", key="y", label="Y", description="."))


async def test_auto_refresh_indicator_reflects_toggle() -> None:
    app = LumlflowApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        header = app.screen.query_one("#app-header")
        assert header.auto_refresh_on is True
        await pilot.press("R")
        await pilot.pause()
        assert app.live_refresh_on is False
        assert header.auto_refresh_on is False


async def test_starts_with_auto_refresh_disabled_when_flag_set() -> None:
    app = LumlflowApp(auto_refresh=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.live_refresh_on is False
        header = app.screen.query_one("#app-header")
        assert header.auto_refresh_on is False


class TestQuitOnHome:
    """`q` on home quits after a confirming re-press; single press stays."""

    async def test_single_q_on_home_stays_and_warns(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            # Still running, quit armed, and the hint was recorded.
            assert app._quit_armed is True
            assert any(
                "again to quit" in message
                for _, _, message in app._recent_messages
            )

    async def test_double_q_on_home_quits(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            await pilot.pause()
            assert app._exit is True

    async def test_q_on_child_screen_pops_and_disarms(self) -> None:
        from lumlflow.tui.screens.experiments import ExperimentsScreen

        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ExperimentsScreen(group_id="g", group_name="g"))
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            # Popped back to home; quit not armed by a child-screen pop.
            assert app._quit_armed is False
            assert app._exit is False


class TestRecentMessages:
    async def test_toasts_are_recorded_and_dialog_opens(self) -> None:
        from lumlflow.tui.widgets.dialogs import MessageLogDialog

        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.show_toast("first message", severity="info")
            app.show_toast("second message", severity="error")
            await pilot.pause()
            messages = [m for _, _, m in app._recent_messages]
            assert "first message" in messages
            assert "second message" in messages
            app.action_messages()
            await pilot.pause()
            assert isinstance(app.screen, MessageLogDialog)
            rows = app.screen.query(".message-log-row")
            rendered = " ".join(str(r.render()) for r in rows)
            assert "second message" in rendered

    async def test_messages_command_registered_for_palette(self) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        assert "global.messages" in registry
        assert registry.get("global.messages").palette_only is True


class TestRefreshIntervalPresets:
    async def test_palette_preset_changes_scheduler_interval(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.refresh_interval == 2.0
            app._invoke_command(app.keymap.get("refresh.interval_10"))
            await pilot.pause()
            assert app.refresh_interval == 10.0
            assert app._refresh_scheduler.interval == 10.0

    async def test_presets_registered(self) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        for seconds in (1, 2, 10):
            assert f"refresh.interval_{seconds}" in registry
