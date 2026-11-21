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

import asyncio
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.schemas.models import UpdateModel
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.live_refresh import LiveRefreshScheduler
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.screens.experiments import ExperimentsScreen
from lumlflow.tui.screens.groups import ALL_EXPERIMENTS_KEY, GroupsScreen
from lumlflow.tui.widgets.dialogs import ConfirmDialog
from textual._context import active_app
from textual.events import Callback
from textual.widgets import DataTable
from textual.worker import WorkerState

from tests.helpers.tui import settle_workers


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


@pytest.fixture
def linked_experiment(tracker: ExperimentTracker, tmp_path: Path) -> str:
    tracker.create_group("models")
    exp_id = tracker.start_experiment(name="run", group="models")
    model_file = tmp_path / "model.luml"
    model_file.write_bytes(b"model-data")
    for name in ("first", "second", "third"):
        tracker.backend.log_model(exp_id, str(model_file), name=name)
    return exp_id


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
    async def test_model_cursor_and_actions_survive_live_refresh(
        self,
        facade: DataFacade,
        linked_experiment: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        app = _make_app(facade, auto_refresh=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentDetailScreen(
                facade=facade, experiment_id=linked_experiment
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#overview-models-table", DataTable)
            table.focus()
            table.move_cursor(row=1)
            await pilot.pause()
            selected_id = _row_keys(table)[1]

            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == selected_id

            facade.update_model(selected_id, UpdateModel(name="renamed")).unwrap()
            screen.refresh_live()
            await pilot.pause()
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == selected_id
            assert table.get_row_at(table.cursor_row)[0].plain == "renamed"
            screen._on_refresh_details_result(Result.failure(500, "refresh failed"))
            assert _row_keys(table)[table.cursor_row] == selected_id

            yanked: list[str] = []
            deleted: list[str] = []
            monkeypatch.setattr(
                app, "yank_to_clipboard", lambda value, **kwargs: yanked.append(value)
            )
            monkeypatch.setattr(screen, "_run_model_delete", deleted.append)
            screen.action_yank_focused_model()
            screen.action_delete_focused_model()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)
            await pilot.press("ctrl+y")
            await pilot.pause()
            assert yanked == [selected_id]
            assert deleted == [selected_id]

    @pytest.mark.parametrize(
        ("model_indexes", "expected_index"),
        [
            ([2, 1, 0], 1),
            ([1, 0, 2], 0),
            ([1, 2], 0),
            ([0, 2], 1),
            ([0], 0),
            ([], None),
        ],
    )
    async def test_model_cursor_tracks_identity_or_clamps_after_removal(
        self,
        facade: DataFacade,
        linked_experiment: str,
        model_indexes: list[int],
        expected_index: int | None,
    ) -> None:
        app = _make_app(facade, auto_refresh=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentDetailScreen(
                facade=facade, experiment_id=linked_experiment
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#overview-models-table", DataTable)
            table.move_cursor(row=1)
            details = facade.get_experiment(linked_experiment).unwrap()
            models = details.models or []
            updated = details.model_copy(
                update={"models": [models[i] for i in model_indexes]}
            )

            screen._on_refresh_details_result(Result.success(updated))
            await pilot.pause()
            if expected_index is None:
                assert table.cursor_type == "none"
                assert _row_keys(table) == ["__no_models__"]
                assert screen._focused_model_row() is None
                screen._on_refresh_details_result(Result.success(details))
                await pilot.pause()
                assert table.cursor_type == "row"
                assert table.cursor_row == 0
            else:
                assert table.cursor_row == expected_index
                assert (
                    _row_keys(table)[table.cursor_row]
                    == models[model_indexes[expected_index]].id
                )
                focused = screen._focused_model_row()
                assert focused is not None
                assert focused.key == _row_keys(table)[table.cursor_row]

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
            assert "loss" in screen._metric_series
            initial_len = len(screen._metric_series["loss"].buckets)
            assert initial_len >= 5
            # Out-of-band write more metric points.
            for step in range(5, 10):
                tracker.log_dynamic(
                    "loss", float(step), step=step, experiment_id=exp_id
                )
            screen.refresh_live()
            for _ in range(5):
                await pilot.pause()
            history = screen._metric_series.get("loss")
            assert history is not None
            assert len(history.buckets) >= initial_len


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


# ---------------------------------------------------------------------------
# A refresh read for a screen that has left
# ---------------------------------------------------------------------------


class TestRefreshAfterItsScreenLeft:
    async def test_a_refresh_started_on_a_detached_screen_is_dropped(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Regression: Textual stops the app's timers only after it has torn
        the screens down, so a refresh tick could start a read for a detached
        screen. Its worker then called `self.app` from the thread, which
        raised `NoActiveAppError` and failed the app (flaky at test exit)."""

        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="run", group=group.name)
        app = _make_app(facade, auto_refresh=False)
        async with app.run_test() as pilot:
            screen = ExperimentDetailScreen(facade=facade, experiment_id=exp_id)
            app.push_screen(screen)
            await settle_workers(pilot)
            app.pop_screen()
            await settle_workers(pilot)
            assert not screen.is_attached

            worker = screen._refresh_details()
            await asyncio.gather(worker.wait(), return_exceptions=True)
            await pilot.pause()

            assert worker.state == WorkerState.SUCCESS
            assert app._exception is None

    async def test_exit_stops_the_refresh_ticks(self, facade: DataFacade) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await settle_workers(pilot)
            assert app._refresh_scheduler._timer is not None

            app.exit()

            assert app._refresh_scheduler._timer is None


class TestRefreshLifetime:
    @pytest.mark.parametrize("screen_kind", ["home", "experiments", "detail"])
    async def test_refresh_starting_after_shutdown_drops_result(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        monkeypatch: pytest.MonkeyPatch,
        screen_kind: str,
    ) -> None:
        group = tracker.create_group("g")
        experiment_id = tracker.start_experiment(name="exp", group="g")
        app = _make_app(facade, auto_refresh=False)
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        errors: list[BaseException] = []
        async with app.run_test() as pilot:
            await settle_workers(pilot)
            if screen_kind == "home":
                screen = app.screen
                callback_name = "_on_refresh_result"
            elif screen_kind == "experiments":
                screen = ExperimentsScreen(group_id=group.id)
                callback_name = "_on_refresh_result"
                await app.push_screen(screen)
            else:
                screen = ExperimentDetailScreen(experiment_id=experiment_id)
                callback_name = "_on_refresh_details_result"
                await app.push_screen(screen)
            await settle_workers(pilot)
            assert screen._facade is None
            assert screen.facade is facade
            callback = Mock()
            monkeypatch.setattr(screen, callback_name, callback)
            run_worker = screen.run_worker

            def delay_worker(work, *args, **kwargs):
                def delayed():
                    started.set()
                    try:
                        assert release.wait(10), "worker was never released"
                        return work()
                    except BaseException as exc:
                        errors.append(exc)
                        raise
                    finally:
                        finished.set()

                return run_worker(delayed, *args, **kwargs)

            monkeypatch.setattr(screen, "run_worker", delay_worker)
            screen.refresh_live()
            try:
                assert await asyncio.to_thread(started.wait, 10)
                await app._shutdown()
                assert not screen.is_attached
            finally:
                release.set()
            assert await asyncio.to_thread(finished.wait, 10)
            assert errors == []
            callback.assert_not_called()

    @pytest.mark.parametrize("screen_kind", ["groups", "experiments", "detail"])
    @pytest.mark.parametrize("leave", ["pop", "unmount", "stop"])
    async def test_blocked_refresh_drops_result_after_leaving(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        monkeypatch: pytest.MonkeyPatch,
        screen_kind: str,
        leave: str,
    ) -> None:
        group = tracker.create_group("g")
        experiment_id = tracker.start_experiment(name="exp", group="g")
        app = _make_app(facade, auto_refresh=False)
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        errors: list[BaseException] = []
        async with app.run_test() as pilot:
            await settle_workers(pilot)
            if screen_kind == "groups":
                screen = GroupsScreen(facade=facade)
                read_name = "list_groups"
                callback_name = "_on_refresh_result"
            elif screen_kind == "experiments":
                screen = ExperimentsScreen(facade=facade, group_id=group.id)
                read_name = "list_group_experiments"
                callback_name = "_on_refresh_result"
            else:
                screen = ExperimentDetailScreen(
                    facade=facade, experiment_id=experiment_id
                )
                read_name = "get_experiment"
                callback_name = "_on_refresh_details_result"
            await app.push_screen(screen)
            await settle_workers(pilot)
            callback = Mock()
            monkeypatch.setattr(screen, callback_name, callback)
            read = getattr(facade, read_name)

            def blocked_read(*args, **kwargs):
                started.set()
                assert release.wait(10), "refresh was never released"
                return read(*args, **kwargs)

            monkeypatch.setattr(facade, read_name, blocked_read)
            run_worker = screen.run_worker

            def observe_worker(work, *args, **kwargs):
                def observed():
                    try:
                        return work()
                    except BaseException as exc:
                        errors.append(exc)
                        raise
                    finally:
                        finished.set()

                return run_worker(observed, *args, **kwargs)

            monkeypatch.setattr(screen, "run_worker", observe_worker)
            if leave == "unmount":

                async def on_unmount(self):
                    release.set()
                    assert await asyncio.to_thread(finished.wait, 10)

                monkeypatch.setattr(
                    type(screen), "on_unmount", on_unmount, raising=False
                )
            screen.refresh_live()
            try:
                assert await asyncio.to_thread(started.wait, 10)
                if leave in {"pop", "unmount"}:
                    await app.pop_screen()
                    await pilot.pause()
                    assert not screen.is_attached
                else:
                    await app._shutdown()
                    assert not app.is_running
            finally:
                release.set()
            assert await asyncio.to_thread(finished.wait, 10)
            assert errors == []
            callback.assert_not_called()

    @pytest.mark.parametrize(
        "screen_kind",
        ["groups", "experiments", "detail", "attachments", "evals", "traces"],
    )
    @pytest.mark.parametrize("leave", ["pop", "stop"])
    async def test_detach_during_result_enqueue_drops_callback(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        monkeypatch: pytest.MonkeyPatch,
        screen_kind: str,
        leave: str,
    ) -> None:
        group = tracker.create_group("g")
        experiment_id = tracker.start_experiment(name="exp", group="g")
        app = _make_app(facade, auto_refresh=False)
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        errors: list[BaseException] = []
        async with app.run_test() as pilot:
            await settle_workers(pilot)
            if screen_kind == "groups":
                screen = GroupsScreen(facade=facade)
                callback_name = "_on_refresh_result"
            elif screen_kind == "experiments":
                screen = ExperimentsScreen(facade=facade, group_id=group.id)
                callback_name = "_on_refresh_result"
            else:
                screen = ExperimentDetailScreen(
                    facade=facade, experiment_id=experiment_id
                )
                callback_name = "_on_refresh_details_result"
            await app.push_screen(screen)
            await settle_workers(pilot)
            if screen_kind in {"attachments", "evals", "traces"}:
                screen = screen.query_one(f"#pane-{screen_kind}-panel")
                callback_name = (
                    "_on_children_result"
                    if screen_kind == "attachments"
                    else "_on_refresh_result"
                )
            callback = Mock()
            monkeypatch.setattr(screen, callback_name, callback)
            check_enabled = screen.check_message_enabled
            main_thread = threading.get_ident()

            def blocked_check(message):
                if (
                    isinstance(message, Callback)
                    and threading.get_ident() != main_thread
                ):
                    assert not screen._closing and not screen._closed
                    started.set()
                    assert release.wait(10), "result enqueue was never released"
                return check_enabled(message)

            monkeypatch.setattr(screen, "check_message_enabled", blocked_check)
            run_worker = screen.run_worker

            def observe_worker(work, *args, **kwargs):
                def observed():
                    try:
                        with pytest.raises(LookupError):
                            active_app.get()
                        return work()
                    except BaseException as exc:
                        errors.append(exc)
                        raise
                    finally:
                        finished.set()

                return run_worker(observed, *args, **kwargs)

            monkeypatch.setattr(screen, "run_worker", observe_worker)
            if screen_kind == "attachments":
                screen._fetch_children(parent_path=None, parent_node_id=None)
            elif screen_kind in {"evals", "traces"}:
                screen._refresh_visible_window(limit=1)
            else:
                screen.refresh_live()
            try:
                assert await asyncio.to_thread(started.wait, 10)
                if leave == "pop":
                    await app.pop_screen()
                    await pilot.pause()
                else:
                    await app._shutdown()
                assert not screen.is_attached
            finally:
                release.set()
            assert await asyncio.to_thread(finished.wait, 10)
            assert errors == []
            if leave == "pop":
                await pilot.pause()
            callback.assert_not_called()

    @pytest.mark.parametrize("trigger", ["_tick", "refresh_now"])
    async def test_scheduler_does_nothing_after_shutdown(
        self, facade: DataFacade, trigger: str
    ) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await settle_workers(pilot)
        assert not app.screen_stack
        getattr(app._refresh_scheduler, trigger)()

    @pytest.mark.parametrize("owner_kind", ["groups", "experiments", "traces", "evals"])
    async def test_discarded_page_fetch_releases_loading(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        monkeypatch: pytest.MonkeyPatch,
        owner_kind: str,
    ) -> None:
        group = tracker.create_group("g")
        experiment_id = tracker.start_experiment(name="exp", group="g")
        app = _make_app(facade, auto_refresh=False)
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()
        errors: list[BaseException] = []
        async with app.run_test() as pilot:
            await settle_workers(pilot)
            if owner_kind == "groups":
                screen = GroupsScreen(facade=facade)
                read_name = "list_groups"
            elif owner_kind == "experiments":
                screen = ExperimentsScreen(facade=facade, group_id=group.id)
                read_name = "list_group_experiments"
            else:
                screen = ExperimentDetailScreen(
                    facade=facade, experiment_id=experiment_id
                )
                read_name = f"list_{owner_kind}"
            await app.push_screen(screen)
            await settle_workers(pilot)
            owner = screen
            if owner_kind in {"traces", "evals"}:
                screen.action_jump_tab(owner_kind)
                await settle_workers(pilot)
                owner = screen.query_one(f"#pane-{owner_kind}-panel")
            assert not app._loading_state
            read = getattr(facade, read_name)

            def blocked_read(*args, **kwargs):
                started.set()
                assert release.wait(10), "page fetch was never released"
                return read(*args, **kwargs)

            monkeypatch.setattr(facade, read_name, blocked_read)
            run_worker = owner.run_worker

            def observe_worker(work, *args, **kwargs):
                def observed():
                    try:
                        return work()
                    except BaseException as exc:
                        errors.append(exc)
                        raise
                    finally:
                        finished.set()

                return run_worker(observed, *args, **kwargs)

            monkeypatch.setattr(owner, "run_worker", observe_worker)
            owner.load_first_page()
            try:
                assert await asyncio.to_thread(started.wait, 10)
                assert app._loading_state
                app._jump_home()
                await pilot.pause()
                assert not owner.is_attached
            finally:
                release.set()
            assert await asyncio.to_thread(finished.wait, 10)
            await pilot.pause()
            assert errors == []
            assert not app._loading_state
