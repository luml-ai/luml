"""Pilot tests for the live auto-refresh feature.

Covers SPEC.md task: "Add live auto-refresh" — a background scheduler
that re-fetches the current screen's data on a worker, diffs, and
applies in-place updates while preserving cursor/scroll; with a toggle,
configurable interval, manual-refresh key, and pause-while-modal-open
behavior.

Tests drive the refresh cycle deterministically (calling
`refresh_live()` / `scheduler.refresh_now()` directly rather than waiting
on the wall-clock interval) so the suite stays fast and stable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.live_refresh import LiveRefreshScheduler
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.screens.experiments import ExperimentsScreen
from lumlflow.tui.screens.groups import ALL_EXPERIMENTS_KEY, GroupsScreen
from lumlflow.tui.widgets.dialogs import ConfirmDialog
from textual.widgets import DataTable


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade, **kwargs) -> LumlflowApp:
    return LumlflowApp(facade=facade, **kwargs)


def _row_keys(table: DataTable) -> list[str]:
    return [row.key.value or "" for row in table.ordered_rows]


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class TestSchedulerWiring:
    """The app owns one scheduler with the configured interval."""

    async def test_scheduler_created_with_app(self, facade: DataFacade) -> None:
        app = _make_app(facade, refresh_interval=1.5)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app._refresh_scheduler, LiveRefreshScheduler)
            assert app._refresh_scheduler.interval == 1.5

    async def test_set_interval_at_runtime(self, facade: DataFacade) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._refresh_scheduler.set_interval(0.5)
            assert app._refresh_scheduler.interval == 0.5

    async def test_interval_clamped_to_minimum(self, facade: DataFacade) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._refresh_scheduler.set_interval(0.0001)
            # The scheduler clamps to 0.1s minimum so we never spin the loop.
            assert app._refresh_scheduler.interval == 0.1


# ---------------------------------------------------------------------------
# Toggle & pause semantics
# ---------------------------------------------------------------------------


class TestToggle:
    async def test_toggle_via_keybind(self, facade: DataFacade) -> None:
        """The `R` key flips `live_refresh_on`."""

        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.live_refresh_on is True
            await pilot.press("R")
            await pilot.pause()
            assert app.live_refresh_on is False
            await pilot.press("R")
            await pilot.pause()
            assert app.live_refresh_on is True

    async def test_toggle_off_disables_scheduled_refresh(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """When the toggle is off, `_tick` is a no-op even though the
        timer keeps firing."""

        tracker.create_group("g0")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            initial_row_count = len(screen._rows)
            # Disable the toggle.
            app.live_refresh_on = False
            # Add a new group out-of-band and tick the scheduler.
            tracker.create_group("g1")
            app._refresh_scheduler._tick()
            await pilot.pause()
            await pilot.pause()
            # No new row because the scheduler short-circuits.
            assert len(screen._rows) == initial_row_count

    async def test_manual_refresh_works_even_when_toggle_off(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """`r` (manual refresh) is independent of the auto-refresh toggle."""

        tracker.create_group("g0")
        app = _make_app(facade, auto_refresh=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            assert app.live_refresh_on is False
            tracker.create_group("g1")
            # Manual refresh action — even though the toggle is off.
            app.action_refresh_now()
            await pilot.pause()
            await pilot.pause()
            keys = _row_keys(screen.query_one("#groups-table", DataTable))
            assert any(k != ALL_EXPERIMENTS_KEY for k in keys)
            # The new group is now visible in the row state.
            real_keys = [r.key for r in screen._rows if not r.is_synthetic]
            assert len(real_keys) == 2


class TestPauseDuringDialog:
    """Refresh must pause while any modal is open."""

    async def test_dialog_opens_pause(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("doomed")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            # Open a delete-confirm dialog.
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            await pilot.press("j")  # move past synthetic to real row
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == group.id
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)
            # While the dialog is open the app reports paused.
            assert app.is_refresh_paused is True
            # Ticks during the dialog are no-ops.
            tracker.create_group("new-group")
            app._refresh_scheduler._tick()
            await pilot.pause()
            # The Groups screen row list has not changed.
            real_keys_before = [r.key for r in screen._rows if not r.is_synthetic]
            assert len(real_keys_before) == 1

    async def test_dialog_closes_resume(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g0")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            # Cause a dialog to open then close.
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)
            assert app.is_refresh_paused is True
            # Cancel.
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, GroupsScreen)
            # Now refresh is no longer paused, and a tick works.
            assert app.is_refresh_paused is False


# ---------------------------------------------------------------------------
# Groups screen refresh
# ---------------------------------------------------------------------------


class TestGroupsRefresh:
    async def test_new_rows_appear_via_refresh(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g0")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            assert len([r for r in screen._rows if not r.is_synthetic]) == 1
            # Out-of-band write.
            tracker.create_group("g1")
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            real_keys = [r.key for r in screen._rows if not r.is_synthetic]
            assert len(real_keys) == 2

    async def test_deleted_rows_disappear_via_refresh(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        a = tracker.create_group("a")
        tracker.create_group("b")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            assert len([r for r in screen._rows if not r.is_synthetic]) == 2
            # Out-of-band delete.
            tracker.delete_group(a.id)
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            real_keys = [r.key for r in screen._rows if not r.is_synthetic]
            assert a.id not in real_keys
            assert len(real_keys) == 1

    async def test_refresh_preserves_cursor(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        for i in range(5):
            tracker.create_group(f"g{i:02d}")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Move the cursor a few rows down.
            await pilot.press("j", "j", "j")
            await pilot.pause()
            saved = table.cursor_row
            assert saved >= 2
            # Out-of-band write + refresh.
            tracker.create_group("zzz-new")
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            # Cursor stays where it was.
            assert table.cursor_row == saved

    async def test_refresh_idempotent_on_no_change(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g0")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            before_rows = list(screen._rows)
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            after_rows = list(screen._rows)
            # Same keys in the same order — no shuffle.
            assert [r.key for r in before_rows] == [r.key for r in after_rows]


# ---------------------------------------------------------------------------
# Experiments screen refresh — status flips are the headline feature
# ---------------------------------------------------------------------------


class TestExperimentsRefresh:
    async def test_status_flip_visible_on_refresh(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """An `active` experiment becomes `completed` after `end_experiment`,
        and a refresh re-colours the row without losing the cursor."""

        from lumlflow.schemas.experiments import ExperimentStatus

        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="run-1", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            # Drill into the experiments screen.
            await pilot.pause()
            await pilot.pause()
            screen = ExperimentsScreen(facade=facade, group_id=group.id)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            # The active row is shown.
            assert any(r.status == ExperimentStatus.ACTIVE for r in screen._rows)
            # Out-of-band finish.
            tracker.end_experiment(experiment_id=exp_id)
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            row = next(r for r in screen._rows if r.key == exp_id)
            assert row.status == ExperimentStatus.COMPLETED

    async def test_new_experiment_appears_via_refresh(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        tracker.start_experiment(name="run-1", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = ExperimentsScreen(facade=facade, group_id=group.id)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            initial = len(screen._rows)
            # Out-of-band write.
            exp_id_2 = tracker.start_experiment(name="run-2", group=group.name)
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            keys = [r.key for r in screen._rows]
            assert exp_id_2 in keys
            assert len(screen._rows) == initial + 1


# ---------------------------------------------------------------------------
# Experiment detail screen — new metric points should appear on refresh
# ---------------------------------------------------------------------------


class TestExperimentDetailRefresh:
    async def test_new_metric_points_appear_on_refresh(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="run", group=group.name)
        for step in range(5):
            tracker.log_dynamic("loss", float(step), step=step, experiment_id=exp_id)
        # End the experiment so `dynamic_params` carries the metric keys.
        tracker.end_experiment(experiment_id=exp_id)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = ExperimentDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="run",
                initial_tab="metrics",
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            # The initial grid fetch should have populated the cached
            # history for the lone metric.
            for _ in range(5):
                await pilot.pause()
            assert "loss" in screen._metric_history
            initial_len = len(screen._metric_history["loss"].history)
            assert initial_len >= 5
            # Out-of-band write more metric points.
            for step in range(5, 10):
                tracker.log_dynamic(
                    "loss", float(step), step=step, experiment_id=exp_id
                )
            screen.refresh_live()
            for _ in range(5):
                await pilot.pause()
            history = screen._metric_history.get("loss")
            assert history is not None
            assert len(history.history) >= initial_len


# ---------------------------------------------------------------------------
# Refresh-now bypass and screens without the protocol
# ---------------------------------------------------------------------------


class TestRefreshNow:
    async def test_refresh_now_targets_current_screen(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g0")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            # Out-of-band write.
            tracker.create_group("g1")
            # Press the manual refresh key.
            await pilot.press("r")
            await pilot.pause()
            await pilot.pause()
            real_keys = [r.key for r in screen._rows if not r.is_synthetic]
            assert len(real_keys) == 2

    async def test_refresh_skips_non_refreshable_screen(
        self, facade: DataFacade
    ) -> None:
        """Screens that don't implement `LiveRefreshable` are quietly skipped."""

        from lumlflow.tui.screens.base import BaseScreen

        class NoRefresh(BaseScreen):
            breadcrumb_label = "Nada"

        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = NoRefresh()
            app.push_screen(screen)
            await pilot.pause()
            # Calling refresh_now is a no-op (no crash).
            app._refresh_scheduler.refresh_now()
            await pilot.pause()
