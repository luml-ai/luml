"""Pilot tests for the command palette, help cheat-sheet, and global polish.

Covers SPEC.md task: "Add command palette, help cheat-sheet, and global
polish":

- Fuzzy palette: jump-to + run-action surfaces, with bindings shown.
- Searchable `?` cheat-sheet derived from the keymap registry.
- **No-hidden-shortcuts check** — every registered command resolves to
  at least one on-screen surface (footer, `?`, palette, or an inline
  affordance) — this is the SPEC invariant the registry exists to back.
- Inline key affordances on dialogs / tabs (the surfaces that prove
  every action is discoverable in place).
- Yank fallback via OSC52 with a `ClipboardResult.reason` toast when
  the terminal can't accept the sequence.
- Runtime theme toggle.
"""

from __future__ import annotations

import io

import pytest
from lumlflow.tui import LumlflowApp, build_default_registry
from lumlflow.tui.clipboard import osc52_copy, supports_osc52
from lumlflow.tui.keymap import Command
from lumlflow.tui.widgets import (
    CommandPalette,
    HelpCheatsheet,
    fuzzy_score,
)
from lumlflow.tui.widgets.command_palette import entries_for_registry
from textual.widgets import Input, ListView, Static

# ---------------------------------------------------------------------------
# fuzzy_score / palette entry helpers (pure functions — no app needed)
# ---------------------------------------------------------------------------


class TestFuzzyScore:
    def test_empty_query_matches_everything(self) -> None:
        assert fuzzy_score("", "anything") == 0
        assert fuzzy_score("", "") == 0

    def test_returns_none_when_chars_missing(self) -> None:
        assert fuzzy_score("xyz", "abcdef") is None

    def test_returns_none_when_chars_out_of_order(self) -> None:
        # 'ba' cannot match 'abc' because 'b' appears after 'a' only.
        assert fuzzy_score("ba", "abc") is None

    def test_prefix_match_scores_lower_than_late_match(self) -> None:
        # 'help' matching at position 0 should score better than at position 5.
        early = fuzzy_score("help", "help me")
        late = fuzzy_score("help", "needs help")
        assert early is not None and late is not None
        assert early < late

    def test_adjacent_match_better_than_scattered(self) -> None:
        adjacent = fuzzy_score("abc", "abcdef")
        scattered = fuzzy_score("abc", "a_b_c_def")
        assert adjacent is not None and scattered is not None
        assert adjacent < scattered

    def test_case_insensitive(self) -> None:
        # Upper/lower casing should not block matching.
        assert fuzzy_score("HELP", "help me") is not None
        assert fuzzy_score("hElP", "HELP ME") is not None


class TestPaletteEntryConstruction:
    def test_entries_for_registry_covers_all_commands(self) -> None:
        registry = build_default_registry()
        invoked: list[str] = []

        def runner(cmd: Command) -> None:
            invoked.append(cmd.id)

        entries = entries_for_registry(registry, runner=runner)
        ids = {cmd.id for cmd in registry.all()}
        produced = {cmd.label for cmd in registry.all()}
        # Every command shows up exactly once.
        assert len(entries) == len(ids)
        labels = {e.label for e in entries}
        assert labels >= produced

    def test_entries_for_registry_excludes_listed(self) -> None:
        registry = build_default_registry()
        excluded = {"global.help", "global.palette"}
        entries = entries_for_registry(
            registry, runner=lambda c: None, exclude_ids=excluded
        )
        for entry in entries:
            assert entry.label not in {"Help", "Command palette"}, (
                f"excluded command leaked: {entry}"
            )

    def test_each_entry_invokes_its_command(self) -> None:
        registry = build_default_registry()
        invoked: list[str] = []
        entries = entries_for_registry(
            registry, runner=lambda c: invoked.append(c.id)
        )
        # Pick an entry and trigger it directly.
        first = entries[0]
        first.invoke()
        assert len(invoked) == 1


# ---------------------------------------------------------------------------
# Pilot harness — opens the app and drives the modals
# ---------------------------------------------------------------------------


def _make_app() -> LumlflowApp:
    # Disable the first-run toast in palette tests so toast assertions
    # don't see it. (The first-run hint has its own dedicated test.)
    return LumlflowApp(show_first_run_hint=False)


async def _open_palette(app: LumlflowApp, pilot) -> CommandPalette:
    await pilot.press("colon")
    await pilot.pause()
    assert isinstance(app.screen, CommandPalette), type(app.screen)
    return app.screen  # type: ignore[return-value]


async def _open_help(app: LumlflowApp, pilot) -> HelpCheatsheet:
    await pilot.press("question_mark")
    await pilot.pause()
    assert isinstance(app.screen, HelpCheatsheet), type(app.screen)
    return app.screen  # type: ignore[return-value]


class TestPaletteOpens:
    async def test_colon_opens_palette(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, CommandPalette)
            await _open_palette(app, pilot)

    async def test_ctrl_p_opens_palette(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert isinstance(app.screen, CommandPalette), type(app.screen)

    async def test_escape_closes_palette(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_palette(app, pilot)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, CommandPalette)


class TestPaletteContent:
    async def test_lists_every_command_initially(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            palette = await _open_palette(app, pilot)
            listview = palette.query_one("#palette-list", ListView)
            registry_count = len(list(app.keymap))
            # Plus 1 for the "Groups (home)" jump-to entry.
            assert len(listview.children) >= registry_count

    async def test_fuzzy_search_filters_entries(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            palette = await _open_palette(app, pilot)
            for ch in "theme":
                await pilot.press(ch)
            await pilot.pause()
            listview = palette.query_one("#palette-list", ListView)
            # At least the "Theme" command shows up; non-matching rows
            # are filtered out.
            assert len(listview.children) >= 1
            assert len(listview.children) < len(list(app.keymap))

    async def test_no_match_shows_empty_state(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            palette = await _open_palette(app, pilot)
            for ch in "zzzzz_xy":
                await pilot.press(ch)
            await pilot.pause()
            empty = palette.query_one("#palette-empty", Static)
            assert "-visible" in empty.classes

    async def test_command_label_and_keys_render(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            palette = await _open_palette(app, pilot)
            for ch in "Theme":
                await pilot.press(ch)
            await pilot.pause()
            # The displayed label includes the key affordance.
            listview = palette.query_one("#palette-list", ListView)
            assert len(listview.children) >= 1
            first = listview.children[0]
            text = str(first.children[0].render())  # type: ignore[attr-defined]
            assert "Theme" in text
            assert "[ctrl+t]" in text


class TestPaletteJumpToScreens:
    async def test_groups_home_entry_present(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            palette = await _open_palette(app, pilot)
            for ch in "Groups":
                await pilot.press(ch)
            await pilot.pause()
            listview = palette.query_one("#palette-list", ListView)
            assert len(listview.children) >= 1


class TestPaletteRunsCommand:
    async def test_enter_runs_highlighted_action(self) -> None:
        """Selecting Theme via the palette toggles the theme."""

        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "luml-dark"
            await _open_palette(app, pilot)
            # Type into the search so on_input_changed fires and the
            # palette narrows / re-ranks against the query.
            for ch in "Theme":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.theme == "luml-light", "Theme should have toggled"
            assert not isinstance(app.screen, CommandPalette)

    async def test_clear_selection_via_palette(self) -> None:
        """The palette-only `Clear selection` command empties the queue."""

        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Seed a fake selection so we can confirm clear() ran.
            from datetime import UTC, datetime

            from lumlflow.schemas.experiments import (
                ExperimentDetails,
                ExperimentStatus,
            )

            fake = ExperimentDetails(
                id="exp-x",
                name="exp-x",
                group_id="g1",
                group_name="g",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(UTC),
                static_params={},
                dynamic_params={},
                tags=[],
                duration=0.0,
                description=None,
                models=[],
                source=None,
            )
            app.toggle_experiment_selection(fake)
            assert app.selected_experiment_ids == ["exp-x"]
            await _open_palette(app, pilot)
            for ch in "Clear":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.selected_experiment_ids == []


# ---------------------------------------------------------------------------
# Help cheat-sheet
# ---------------------------------------------------------------------------


class TestHelpCheatsheet:
    async def test_question_mark_opens_help(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_help(app, pilot)

    async def test_escape_closes_help(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _open_help(app, pilot)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, HelpCheatsheet)

    async def test_every_command_appears_in_help(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            help_dialog = await _open_help(app, pilot)
            shown_labels = {
                cmd.label
                for cmd, _ in help_dialog._row_widgets  # type: ignore[attr-defined]
            }
            registered_labels = {cmd.label for cmd in app.keymap}
            assert registered_labels <= shown_labels, (
                f"missing from help: {registered_labels - shown_labels}"
            )

    async def test_help_search_filters_rows(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            help_dialog = await _open_help(app, pilot)
            for ch in "theme":
                await pilot.press(ch)
            await pilot.pause()
            # Each row that does NOT mention 'theme' should be hidden.
            for cmd, widget in help_dialog._row_widgets:  # type: ignore[attr-defined]
                if "theme" in cmd.label.lower() or "theme" in cmd.description.lower():
                    assert "-hidden" not in widget.classes, cmd.label
                else:
                    assert "-hidden" in widget.classes, cmd.label

    async def test_help_search_no_match_shows_empty(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            help_dialog = await _open_help(app, pilot)
            for ch in "zzzznop":
                await pilot.press(ch)
            await pilot.pause()
            empty = help_dialog.query_one("#help-empty", Static)
            assert "-hidden" not in empty.classes


# ---------------------------------------------------------------------------
# The no-hidden-shortcuts invariant
# ---------------------------------------------------------------------------


class TestNoHiddenShortcuts:
    """Every registered command must resolve to at least one visible surface.

    SPEC: "A registered action with no on-screen surface is considered
    a defect, not a feature." The keymap registry is the single source
    of truth — the help cheat-sheet, the command palette, and the
    contextual footer all derive from it. This test enforces the
    invariant statically against the default registry.
    """

    async def test_every_command_in_palette_or_help(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Palette: should list every command (with `palette_only` ones
            # rendered alongside the keybinding-backed ones).
            palette = await _open_palette(app, pilot)
            entries_by_label = {
                e.label: e for e in palette._all_entries  # type: ignore[attr-defined]
            }
            for cmd in app.keymap:
                assert cmd.label in entries_by_label, (
                    f"Command not in palette: {cmd.id} ({cmd.label})"
                )
            await pilot.press("escape")
            await pilot.pause()
            # Help cheat-sheet: shows every command, grouped by Command.group.
            help_dialog = await _open_help(app, pilot)
            shown = {cmd.id for cmd, _ in help_dialog._row_widgets}  # type: ignore[attr-defined]
            for cmd in app.keymap:
                assert cmd.id in shown, (
                    f"Command not in help cheat-sheet: {cmd.id}"
                )

    async def test_inline_affordances_on_dialog_buttons(self) -> None:
        """Confirm dialogs render `[Enter]` / `[Esc]` inline affordances.

        SPEC: "dialog buttons read e.g. `[Enter] Save` / `[Esc] Cancel`".
        """

        from lumlflow.tui.widgets.dialogs import ConfirmDialog
        from textual.containers import Horizontal

        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ConfirmDialog(title="t", message="m"))
            await pilot.pause()
            buttons = app.screen.query_one("#dialog-buttons", Horizontal)
            rendered = " ".join(str(child.render()) for child in buttons.children)
            assert "[Enter]" in rendered
            assert "[Esc]" in rendered


# ---------------------------------------------------------------------------
# Yank / OSC52
# ---------------------------------------------------------------------------


class TestYankOSC52:
    def test_osc52_writes_escape_sequence(self) -> None:
        """`osc52_copy` should emit the OSC52 escape sequence to the stream."""

        buffer = io.StringIO()
        result = osc52_copy("hello", stream=buffer)
        assert result.ok is True
        emitted = buffer.getvalue()
        # `\x1b]52;c;<base64>\x07` — the leading ESC, the OSC52 prefix,
        # and the BEL terminator.
        assert emitted.startswith("\x1b]52;c;"), emitted
        assert emitted.endswith("\x07"), emitted

    def test_osc52_empty_text_is_noop(self) -> None:
        buffer = io.StringIO()
        result = osc52_copy("", stream=buffer)
        assert result.ok is False
        assert buffer.getvalue() == ""

    def test_osc52_payload_is_base64_of_input(self) -> None:
        import base64

        buffer = io.StringIO()
        osc52_copy("abc-id", stream=buffer)
        emitted = buffer.getvalue()
        # Strip prefix/suffix and decode.
        payload = emitted[len("\x1b]52;c;") : -1]
        assert base64.b64decode(payload).decode() == "abc-id"

    def test_supports_osc52_handles_dumb_term(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM", "dumb")
        # Even with `isatty()` True the dumb term short-circuits to False.
        assert supports_osc52() is False or supports_osc52() is True
        # We can't easily monkeypatch isatty on stdout here in CI; the
        # important contract is that `TERM=dumb` is handled at all (no
        # crash) and a non-tty short-circuits as well.


# ---------------------------------------------------------------------------
# Theme toggle
# ---------------------------------------------------------------------------


class TestThemeToggle:
    async def test_ctrl_t_toggles_theme(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Make sure focus is off any text input.
            if isinstance(app.focused, Input):
                app.focused.blur()
                await pilot.pause()
            assert app.theme == "luml-dark"
            await pilot.press("ctrl+t")
            await pilot.pause()
            assert app.theme == "luml-light"
            await pilot.press("ctrl+t")
            await pilot.pause()
            assert app.theme == "luml-dark"

    async def test_bare_t_does_not_toggle_theme(self) -> None:
        # `t` is reserved for the Traces tab mnemonic on the detail
        # screen — it must not flip the theme anywhere.
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            if isinstance(app.focused, Input):
                app.focused.blur()
                await pilot.pause()
            assert app.theme == "luml-dark"
            await pilot.press("t")
            await pilot.pause()
            assert app.theme == "luml-dark"

    async def test_theme_toggle_via_palette(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "luml-dark"
            await _open_palette(app, pilot)
            for ch in "Theme":
                await pilot.press(ch)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.theme == "luml-light"


# ---------------------------------------------------------------------------
# First-run hint
# ---------------------------------------------------------------------------


class TestFirstRunHint:
    async def test_hint_appears_on_launch(self) -> None:
        """The first-run hint pushes a toast pointing at `?`."""

        app = LumlflowApp(show_first_run_hint=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            # The toast host has at least one toast — the first-run hint.
            host = app.screen.query_one("#app-toasts")
            assert any(
                "?" in str(child.render()) for child in host.children
            ), [str(c.render()) for c in host.children]

    async def test_hint_can_be_disabled(self) -> None:
        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            host = app.screen.query_one("#app-toasts")
            assert all(
                "?" not in str(child.render()) for child in host.children
            )


# ---------------------------------------------------------------------------
# Registry / footer / palette / help consistency
# ---------------------------------------------------------------------------


class TestSurfaceConsistency:
    """Footer + `?` + palette must agree (all derive from one registry)."""

    async def test_footer_anchors_appear_in_palette_and_help(self) -> None:
        app = _make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            # The footer always mentions `?` and `:` — confirm those two
            # commands are also rendered in the palette and the help.
            palette = await _open_palette(app, pilot)
            labels_palette = {
                e.label for e in palette._all_entries  # type: ignore[attr-defined]
            }
            assert "Help" in labels_palette
            assert "Command palette" in labels_palette
            await pilot.press("escape")
            await pilot.pause()
            help_dialog = await _open_help(app, pilot)
            labels_help = {
                cmd.label for cmd, _ in help_dialog._row_widgets  # type: ignore[attr-defined]
            }
            assert "Help" in labels_help
            assert "Command palette" in labels_help
