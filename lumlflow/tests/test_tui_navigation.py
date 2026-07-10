"""Tests for the TUI navigation/interaction model.

Covers SPEC.md task: "Fix TUI navigation and interaction model":

- Enter drills in from every focused list/table/tree (groups, experiments,
  traces) — DataTable's built-in `select_cursor` binding used to swallow
  Enter.
- Screen history is Ctrl+arrows only; plain arrows stay in-widget.
- Esc/`q` is a no-op on the Groups home screen — the bare
  `len(screen_stack) > 1` check used to pop home and reveal Textual's
  blank `_default` screen.
- Back-navigation preserves cursor position (screens stay alive in
  Textual's stack while a child is on top).
- Clicking a non-leaf breadcrumb segment navigates up to that level.

All tests use Textual's headless `App.run_test()` + `Pilot` against an
in-memory seeded `ExperimentTracker` so the suite stays deterministic
and fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.screens.experiments import ExperimentsScreen
from lumlflow.tui.screens.groups import GroupsScreen
from lumlflow.tui.screens.trace_detail import TraceDetailScreen
from lumlflow.tui.widgets.breadcrumb import Breadcrumb, BreadcrumbSegment
from lumlflow.tui.widgets.traces_panel import TracesPanel
from textual.widgets import DataTable


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade, show_first_run_hint=False)


def _seed_group_and_experiment(
    tracker: ExperimentTracker,
    *,
    group: str = "g",
    experiment: str = "exp",
) -> tuple[str, str]:
    g = tracker.create_group(group)
    exp_id = tracker.start_experiment(name=experiment, group=group)
    tracker.end_experiment(experiment_id=exp_id)
    return g.id, exp_id


def _seed_trace(
    tracker: ExperimentTracker,
    *,
    experiment_id: str,
    trace_id: str = "tr-1",
) -> str:
    tracker.log_span(
        trace_id=trace_id,
        span_id="s-root",
        name="root",
        start_time_unix_nano=0,
        end_time_unix_nano=1_000_000,
        experiment_id=experiment_id,
    )
    return trace_id


class TestEnterDrillsIn:
    """SPEC scenario: Enter drills into a focused list."""

    async def test_enter_on_groups_drills_in(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Cursor lands on the synthetic All Experiments row first.
            await pilot.press("enter")
            await pilot.pause()
            # Enter must navigate, identical to `→` — DataTable's own
            # `select_cursor` binding used to absorb Enter.
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_enter_on_experiments_drills_in(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_group_and_experiment(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            # Drill into the group first.
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            # Skip the synthetic All row, drill into the real group.
            table.move_cursor(row=1)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            exp_table = app.screen.query_one("#experiments-table", DataTable)
            exp_table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentDetailScreen)

    async def test_enter_on_traces_drills_in(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _group_id, exp_id = _seed_group_and_experiment(tracker)
        _seed_trace(tracker, experiment_id=exp_id)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Push the experiment detail directly so we are testing the
            # Enter-drill-in contract specifically, not navigation depth.
            detail = ExperimentDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                group_name="g",
            )
            app.push_screen(detail)
            await pilot.pause()
            await pilot.pause()
            detail.action_jump_tab("traces")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            panel = detail.query_one("#pane-traces-panel", TracesPanel)
            table = panel.query_one("#traces-table", DataTable)
            assert table.row_count == 1
            table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, TraceDetailScreen)


class TestBackOnHomeIsNoOp:
    """SPEC scenario: Back never reveals the blank screen."""

    async def test_escape_on_home_stays_on_home(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            await pilot.press("escape")
            await pilot.pause()
            # Must still be on the Groups home — Textual's blank
            # `_default` screen is not a valid landing.
            assert isinstance(app.screen, GroupsScreen)

    async def test_q_on_home_stays_on_home(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)

    async def test_escape_on_child_pops_to_home(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            home = app.screen
            assert isinstance(home, GroupsScreen)
            table = home.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            # Esc on a child pops back to home — but Esc on home from
            # the test above stays put.
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)

    async def test_plain_arrows_do_not_navigate_screens(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Screen history is Ctrl+arrows only. Plain `←`/`→` stay
        # in-widget (cursor / scroll) — they must neither pop nor push
        # screens no matter where focus is.
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            home = app.screen
            assert isinstance(home, GroupsScreen)
            home.query_one("#groups-table", DataTable).focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            await pilot.press("left")
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            # `→` no longer drills in either — Enter is the open key.
            await pilot.press("ctrl+left")
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            await pilot.press("right")
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)


class TestBackPreservesCursor:
    """SPEC scenario: Back from a child preserves list state."""

    async def test_cursor_survives_drill_and_back(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Seed enough groups to make cursor movement meaningful.
        for i in range(5):
            tracker.create_group(f"grp-{i:02d}")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            home = app.screen
            assert isinstance(home, GroupsScreen)
            table = home.query_one("#groups-table", DataTable)
            table.focus()
            # Move cursor to row 3 (past the synthetic All Experiments
            # row and a few real groups).
            target_row = 3
            table.move_cursor(row=target_row)
            await pilot.pause()
            assert table.cursor_row == target_row
            # Drill in.
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            # Pop back.
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            # Home is back and the cursor is where we left it.
            assert isinstance(app.screen, GroupsScreen)
            table = app.screen.query_one("#groups-table", DataTable)
            assert table.cursor_row == target_row


class TestBreadcrumbClickNavigatesUp:
    """SPEC scenario: Breadcrumb navigates up."""

    async def test_click_groups_segment_pops_to_home(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_group_and_experiment(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            # Drill from home → experiments.
            home = app.screen
            assert isinstance(home, GroupsScreen)
            table = home.query_one("#groups-table", DataTable)
            table.focus()
            table.move_cursor(row=1)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            # Simulate a click on the leftmost ("Groups") segment.
            app.on_breadcrumb_segment_clicked(
                Breadcrumb.SegmentClicked(BreadcrumbSegment("Groups"), 0)
            )
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)

    async def test_click_intermediate_segment_pops_to_that_level(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_group_and_experiment(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            # Drill from home → experiments → experiment detail.
            home = app.screen
            assert isinstance(home, GroupsScreen)
            table = home.query_one("#groups-table", DataTable)
            table.focus()
            table.move_cursor(row=1)  # the seeded group, not the synthetic row
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            exp_table = app.screen.query_one("#experiments-table", DataTable)
            exp_table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentDetailScreen)
            # Clicking the group segment ("g") pops the detail and lands
            # on the experiments list — not on home, not on detail.
            app.on_breadcrumb_segment_clicked(
                Breadcrumb.SegmentClicked(BreadcrumbSegment("g"), 1)
            )
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_click_leaf_segment_is_noop(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            # The home leaf is "Groups"; clicking it stays put.
            app.on_breadcrumb_segment_clicked(
                Breadcrumb.SegmentClicked(BreadcrumbSegment("Groups"), 0)
            )
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)


class TestNavigateUpAction:
    """The palette-only `navigation.up` action is wired and discoverable."""

    async def test_navigate_up_action_pops_one_screen(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            home = app.screen
            assert isinstance(home, GroupsScreen)
            table = home.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            app.action_navigate_up()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)

    async def test_navigate_up_on_home_is_noop(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            app.action_navigate_up()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)

    async def test_navigation_up_command_registered(
        self, facade: DataFacade
    ) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        # The new palette-only entry exists so `?` and `:` surface it.
        assert "navigation.up" in registry
        cmd = registry.get("navigation.up")
        assert cmd.palette_only is True
        # Sanity: the action method exists on the app.
        app = _make_app(facade)
        assert hasattr(app, "action_navigate_up")


class TestScreenHistoryBackForward:
    """Ctrl+←/→ walk the screen stack backward and forward.

    Back (also Esc/`q`) records each popped screen so Forward can
    re-push it; a fresh drill-in invalidates the forward history.
    """

    def _drill_to_detail(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> tuple[str, str]:
        group_id, exp_id = _seed_group_and_experiment(tracker)
        return group_id, exp_id

    async def test_ctrl_left_then_ctrl_right_round_trips(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group_id, exp_id = self._drill_to_detail(facade, tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(
                ExperimentsScreen(
                    facade=facade, group_id=group_id, group_name="g"
                )
            )
            await pilot.pause()
            app.push_screen(
                ExperimentDetailScreen(
                    facade=facade,
                    experiment_id=exp_id,
                    experiment_name="exp",
                    group_name="g",
                )
            )
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentDetailScreen)
            # Back to the list.
            await pilot.press("ctrl+left")
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            assert len(app._forward_stack) == 1
            # The recorded screen must be kept alive (installed) — a
            # removed screen re-pushed by Forward would sit dead on the
            # stack and swallow every key (the ctrl+→ freeze).
            recorded = app._forward_stack[0]
            assert recorded.is_running
            assert app.is_screen_installed(recorded)
            # Forward re-pushes the detail screen.
            await pilot.press("ctrl+right")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentDetailScreen)
            assert app._forward_stack == []
            # The revived screen is live and no longer installed, so a
            # later Back can dispose of it normally.
            assert app.screen.is_running
            assert not app.is_screen_installed(app.screen)
            # And the app still responds: Esc pops back to the list.
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_ctrl_right_is_noop_without_history(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            await pilot.press("ctrl+right")
            await pilot.pause()
            # Nothing to redo: stay on home, no crash.
            assert isinstance(app.screen, GroupsScreen)
            assert app._forward_stack == []

    async def test_fresh_drill_in_clears_forward_history(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group_id, exp_id = self._drill_to_detail(facade, tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(
                ExperimentsScreen(
                    facade=facade, group_id=group_id, group_name="g"
                )
            )
            await pilot.pause()
            # Back to home records the list in the forward stack.
            await pilot.press("ctrl+left")
            await pilot.pause()
            assert len(app._forward_stack) == 1
            recorded = app._forward_stack[0]
            assert app.is_screen_installed(recorded)
            # A new drill-in invalidates the forward history and
            # releases the screen it kept alive.
            app.push_screen(
                ExperimentsScreen(
                    facade=facade, group_id=group_id, group_name="g"
                )
            )
            await pilot.pause()
            await pilot.pause()
            assert app._forward_stack == []
            assert not app.is_screen_installed(recorded)
            assert not recorded.is_running

    async def test_forward_command_registered(
        self, facade: DataFacade
    ) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        assert "global.forward" in registry
        cmd = registry.get("global.forward")
        assert "ctrl+right" in cmd.display_keys
        # Ctrl+Left is a Back alias so both Ctrl+arrows drive history.
        back = registry.get("global.back")
        assert "ctrl+left" in back.display_keys
        # Plain arrows are in-widget keys and must not drive history.
        assert "left" not in back.display_keys
        assert "right" not in registry.get("list.open").display_keys
        app = _make_app(facade)
        assert hasattr(app, "action_forward")
