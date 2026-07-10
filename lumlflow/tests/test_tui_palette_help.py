"""Pilot tests for command palette / help cheat-sheet integrations.

Complements `test_tui_palette.py` (which covers the palette / cheatsheet
widgets and the global polish primitives in isolation) by verifying the
**integration** points:

- Each list screen (Groups, Experiments) contributes its loaded rows
  as palette jump-to entries so the user can drill into a group or
  experiment by name without leaving the keyboard.
- Invoking those palette entries actually drills into the right
  downstream screen.
- The palette can dispatch global-scope and list-scope commands via the
  candidate-action-name fallback so `Theme`, `Compare`, `Edit`, etc.
  work from the palette without each screen registering both
  `action_global_toggle_theme` *and* `action_toggle_theme`.

Tests use Textual's headless `App.run_test()` + Pilot against an
in-memory seeded `ExperimentTracker`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.experiments import ExperimentsScreen
from lumlflow.tui.screens.groups import GroupsScreen
from lumlflow.tui.widgets.command_palette import CommandPalette


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade, show_first_run_hint=False)


def _seed(tracker: ExperimentTracker) -> dict[str, str]:
    """Seed two groups, each with an experiment, and return name→id maps."""

    g_alpha = tracker.create_group("alpha")
    g_beta = tracker.create_group("beta")
    e_one = tracker.start_experiment(name="exp-one", group="alpha")
    e_two = tracker.start_experiment(name="exp-two", group="beta")
    return {
        "group_alpha": g_alpha.id,
        "group_beta": g_beta.id,
        "exp_one": e_one,
        "exp_two": e_two,
    }


# ---------------------------------------------------------------------------
# Groups screen contributes jump-to entries
# ---------------------------------------------------------------------------


class TestGroupsScreenPaletteEntries:
    async def test_each_loaded_group_appears_in_palette(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Per SPEC: "jump-to: any screen, or a group/experiment by name"."""

        _seed(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("colon")
            await pilot.pause()
            palette = app.screen
            assert isinstance(palette, CommandPalette)
            labels = {e.label for e in palette._all_entries}
            assert "alpha" in labels
            assert "beta" in labels

    async def test_palette_jump_to_group_drills_in(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Invoking a group entry drills into the experiments screen."""

        _seed(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("colon")
            await pilot.pause()
            palette = app.screen
            assert isinstance(palette, CommandPalette)
            entry = next(
                e for e in palette._all_entries if e.label == "alpha"
            )
            palette.dismiss(None)
            await pilot.pause()
            entry.invoke()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_synthetic_all_experiments_appears(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("colon")
            await pilot.pause()
            palette = app.screen
            assert isinstance(palette, CommandPalette)
            labels = {e.label for e in palette._all_entries}
            assert "All experiments" in labels


# ---------------------------------------------------------------------------
# Experiments screen contributes jump-to entries
# ---------------------------------------------------------------------------


class TestExperimentsScreenPaletteEntries:
    async def test_loaded_experiments_appear_in_palette(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        ids = _seed(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            app.push_screen(
                ExperimentsScreen(
                    facade=facade,
                    group_id=ids["group_alpha"],
                    group_name="alpha",
                )
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("colon")
            await pilot.pause()
            palette = app.screen
            assert isinstance(palette, CommandPalette)
            labels = " ".join(e.label for e in palette._all_entries)
            assert "exp-one" in labels


# ---------------------------------------------------------------------------
# Palette dispatches to action methods via candidate-name fallback
# ---------------------------------------------------------------------------


class TestPaletteActionDispatch:
    async def test_global_toggle_theme_runs_via_palette(
        self, facade: DataFacade
    ) -> None:
        """The Theme command id is `global.toggle_theme` but the action
        method is `action_toggle_theme`; the dispatcher must try the
        un-namespaced fallback so the palette path stays in sync with
        the keybinding path.
        """

        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            initial = app.theme
            await pilot.press("colon")
            await pilot.pause()
            palette = app.screen
            assert isinstance(palette, CommandPalette)
            theme_entry = next(
                e for e in palette._all_entries
                if e.label == "Theme" and e.kind == "command"
            )
            palette.dismiss(None)
            await pilot.pause()
            theme_entry.invoke()
            await pilot.pause()
            assert app.theme != initial

    async def test_list_edit_runs_via_palette_with_suffix_fallback(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """`list.edit` should resolve to `action_edit_focused` on the
        groups screen via the `_focused` suffix candidate.
        """

        _seed(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            # Focus a real group row (skip the synthetic All).
            screen.action_cursor_down()
            await pilot.pause()
            await pilot.press("colon")
            await pilot.pause()
            palette = app.screen
            assert isinstance(palette, CommandPalette)
            edit_entry = next(
                e for e in palette._all_entries
                if e.label == "Edit" and e.kind == "command"
            )
            palette.dismiss(None)
            await pilot.pause()
            edit_entry.invoke()
            await pilot.pause()
            # The action should have pushed an edit dialog.
            from lumlflow.tui.widgets.dialogs import EditEntityDialog

            assert isinstance(app.screen, EditEntityDialog)


# ---------------------------------------------------------------------------
# Candidate action name resolution
# ---------------------------------------------------------------------------


class TestCandidateActionNames:
    def test_namespaced_id_yields_short_and_long_forms(self) -> None:
        names = LumlflowApp._candidate_action_names("global.toggle_theme")
        assert "action_global_toggle_theme" in names
        assert "action_toggle_theme" in names

    def test_list_verb_yields_focused_suffix(self) -> None:
        names = LumlflowApp._candidate_action_names("list.edit")
        assert "action_edit_focused" in names

    def test_unnamespaced_id_yields_single_candidate(self) -> None:
        names = LumlflowApp._candidate_action_names("plainverb")
        assert "action_plainverb" in names


class TestAvailableHereSection:
    """`?` leads with the commands that work on the current screen."""

    async def test_cheatsheet_leads_with_contextual_commands(self) -> None:
        from lumlflow.tui.widgets.help_cheatsheet import HelpCheatsheet

        app = LumlflowApp(show_first_run_hint=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Home is the Groups list → scopes (global, list, actions).
            await pilot.press("question_mark")
            await pilot.pause()
            sheet = app.screen
            assert isinstance(sheet, HelpCheatsheet)
            labels = [
                str(w.render())
                for w in sheet.query(".help-group-label")
            ]
            assert labels and "Available here" in labels[0]
            # The section holds contextual (non-global) commands.
            rows = sheet.query(".help-row")
            assert rows

    async def test_no_contextual_section_without_scopes(self) -> None:
        from lumlflow.tui.keymap import build_default_registry
        from lumlflow.tui.widgets.help_cheatsheet import HelpCheatsheet

        registry = build_default_registry()
        sheet = HelpCheatsheet(registry)
        groups = sheet._grouped_commands()
        assert "Available here" not in groups

    async def test_contextual_section_matches_scopes(self) -> None:
        from lumlflow.tui.keymap import build_default_registry
        from lumlflow.tui.widgets.help_cheatsheet import HelpCheatsheet

        registry = build_default_registry()
        sheet = HelpCheatsheet(
            registry, active_scopes=("global", "attachments")
        )
        groups = sheet._grouped_commands()
        here = groups.get("Available here")
        assert here is not None
        ids = {cmd.id for cmd in here}
        assert "attachments.save" in ids
        # Global commands are always available and stay in their own
        # groups; list-scope commands are not active here.
        assert all(cmd.scope == "attachments" for cmd in here)
