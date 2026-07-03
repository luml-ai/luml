"""Unit tests for the metric grid + zoom widgets.

These tests focus on the widgets themselves, in isolation from the
experiment-detail screen — the integration with the screen
(`refresh_live`, message routing, keymap binding) is covered by
``tests/test_tui_experiment_detail.py``. Here we verify the
presentational contract: grid cells map to keys, history flows into
the right cell, the zoom view toggles transform the rendered series,
empty states render, and zoom toggles fire ``ToggleChanged`` messages
so the screen can react.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from lumlflow.schemas.experiments import ExperimentMetricHistory, MetricPoint
from lumlflow.tui.widgets.metric_grid import (
    MetricCell,
    MetricGrid,
    MetricZoomView,
    _exponential_moving_average,
    _filter_positive,
    _sanitize_metric_key,
)
from textual.app import App, ComposeResult
from textual.widgets import Static

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestSanitizeMetricKey:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("loss", "loss"),
            ("val/accuracy", "val_accuracy"),
            ("train.acc", "train_acc"),
            ("lr-1", "lr-1"),
            ("a b c", "a_b_c"),
        ],
    )
    def test_replaces_unsafe_chars(self, raw: str, expected: str) -> None:
        assert _sanitize_metric_key(raw) == expected


class TestExponentialMovingAverage:
    def test_empty_returns_empty(self) -> None:
        assert _exponential_moving_average([]) == []

    def test_first_value_unchanged(self) -> None:
        out = _exponential_moving_average([1.0, 2.0, 3.0], alpha=0.5)
        assert out[0] == 1.0

    def test_smooths_a_step_change(self) -> None:
        # alpha=0.5: each value is the midpoint of the previous EMA + raw.
        out = _exponential_moving_average([0.0, 10.0, 10.0, 10.0], alpha=0.5)
        assert out[0] == 0.0
        assert out[1] == 5.0
        assert out[2] == 7.5
        assert out[3] == 8.75

    def test_higher_alpha_reacts_faster(self) -> None:
        low = _exponential_moving_average([0.0, 100.0], alpha=0.1)
        high = _exponential_moving_average([0.0, 100.0], alpha=0.9)
        assert high[1] > low[1]


class TestFilterPositive:
    def test_drops_non_positive(self) -> None:
        xs, ys = _filter_positive([1, 2, 3, 4], [10.0, -1.0, 0.0, 5.0])
        assert xs == [1, 4]
        assert ys == [10.0, 5.0]

    def test_all_positive_passes_through(self) -> None:
        xs, ys = _filter_positive([1, 2], [1.0, 2.0])
        assert xs == [1, 2]
        assert ys == [1.0, 2.0]

    def test_all_dropped(self) -> None:
        xs, ys = _filter_positive([1, 2], [0.0, -1.0])
        assert xs == []
        assert ys == []


# ---------------------------------------------------------------------------
# Widget harnesses
# ---------------------------------------------------------------------------


class _GridApp(App[None]):
    """Minimal app harness that hosts a ``MetricGrid`` for Pilot testing."""

    def compose(self) -> ComposeResult:
        yield MetricGrid(id="grid-under-test")


class _ZoomApp(App[None]):
    """Minimal app harness that hosts a ``MetricZoomView``."""

    def compose(self) -> ComposeResult:
        yield MetricZoomView(id="zoom-under-test")


def _history(
    key: str, points: int = 5, subsampled: bool = False
) -> ExperimentMetricHistory:
    """Build a deterministic ExperimentMetricHistory for tests."""

    return ExperimentMetricHistory(
        experiment_id="exp",
        key=key,
        subsampled=subsampled,
        history=[
            MetricPoint(
                value=float(i),
                step=i,
                logged_at=datetime(2026, 1, 1, 0, 0, i, tzinfo=UTC),
            )
            for i in range(points)
        ],
    )


# ---------------------------------------------------------------------------
# MetricGrid behavior
# ---------------------------------------------------------------------------


class TestMetricGrid:
    async def test_starts_empty(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            assert grid.metric_keys == ()
            assert list(grid.query(MetricCell)) == []
            empty = grid.query_one("#metric-grid-empty", Static)
            assert "-hidden" not in empty.classes

    async def test_set_metric_keys_mounts_one_cell_per_key(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            grid.set_metric_keys(["loss", "acc", "f1"])
            await pilot.pause()
            cells = list(grid.query(MetricCell))
            assert [c.metric_key for c in cells] == ["loss", "acc", "f1"]
            assert grid.metric_keys == ("loss", "acc", "f1")
            empty = grid.query_one("#metric-grid-empty", Static)
            assert "-hidden" in empty.classes

    async def test_set_metric_keys_drops_removed(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            grid.set_metric_keys(["loss", "acc"])
            await pilot.pause()
            assert {c.metric_key for c in grid.query(MetricCell)} == {
                "loss",
                "acc",
            }
            grid.set_metric_keys(["loss"])
            await pilot.pause()
            assert {c.metric_key for c in grid.query(MetricCell)} == {"loss"}

    async def test_apply_history_routes_to_cell(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            grid.set_metric_keys(["loss"])
            await pilot.pause()
            grid.apply_history(_history("loss", points=4))
            await pilot.pause()
            cell = next(iter(grid.query(MetricCell)))
            assert cell._history is not None
            assert cell._history.key == "loss"
            assert len(cell._history.history) == 4

    async def test_apply_history_for_unknown_key_is_noop(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            grid.set_metric_keys(["loss"])
            await pilot.pause()
            # Should not raise.
            grid.apply_history(_history("acc"))
            await pilot.pause()

    async def test_history_needed_posted_for_new_cells(self) -> None:
        """Adding cells should announce ``HistoryNeeded`` for each one."""

        received: list[tuple[str, int]] = []

        class _CaptureApp(App[None]):
            def compose(self) -> ComposeResult:
                yield MetricGrid(id="grid")

            def on_metric_grid_history_needed(
                self, event: MetricGrid.HistoryNeeded
            ) -> None:
                received.append((event.metric_key, event.max_points))
                event.stop()

        async with _CaptureApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid", MetricGrid)
            grid.set_metric_keys(["a", "b"])
            for _ in range(3):
                await pilot.pause()
            keys = [k for k, _ in received]
            assert set(keys) == {"a", "b"}
            for _, max_points in received:
                assert max_points >= 40

    async def test_request_refresh_visible_re_emits(self) -> None:
        received: list[str] = []

        class _CaptureApp(App[None]):
            def compose(self) -> ComposeResult:
                yield MetricGrid(id="grid")

            def on_metric_grid_history_needed(
                self, event: MetricGrid.HistoryNeeded
            ) -> None:
                received.append(event.metric_key)
                event.stop()

        async with _CaptureApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid", MetricGrid)
            grid.set_metric_keys(["loss"])
            for _ in range(3):
                await pilot.pause()
            received.clear()
            grid.request_refresh_visible()
            for _ in range(3):
                await pilot.pause()
            assert received == ["loss"]


# ---------------------------------------------------------------------------
# MetricCell behavior
# ---------------------------------------------------------------------------


class TestMetricCell:
    async def test_zoom_request_emitted_on_action(self) -> None:
        """A cell ``ZoomRequested`` should bubble as ``MetricGrid.ZoomRequested``."""

        received: list[str] = []

        class _CaptureApp(App[None]):
            def compose(self) -> ComposeResult:
                yield MetricGrid(id="grid")

            def on_metric_grid_zoom_requested(
                self, event: MetricGrid.ZoomRequested
            ) -> None:
                received.append(event.metric_key)
                event.stop()

        async with _CaptureApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid", MetricGrid)
            grid.set_metric_keys(["loss"])
            for _ in range(3):
                await pilot.pause()
            cell = grid.query_one(MetricCell)
            cell.action_zoom()
            for _ in range(3):
                await pilot.pause()
            assert received == ["loss"]


# ---------------------------------------------------------------------------
# MetricZoomView behavior
# ---------------------------------------------------------------------------


class TestMetricZoomView:
    async def test_initial_state(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            assert zoom.metric_key is None
            assert zoom.smoothing is False
            assert zoom.log_scale is False
            assert zoom.x_axis == "step"

    async def test_set_metric_key_resets_toggles(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            zoom.action_toggle_smoothing()
            zoom.action_toggle_log_scale()
            zoom.action_toggle_x_axis()
            assert zoom.smoothing is True
            assert zoom.log_scale is True
            assert zoom.x_axis == "wall_clock"
            zoom.set_metric_key("acc")
            assert zoom.smoothing is False
            assert zoom.log_scale is False
            assert zoom.x_axis == "step"

    async def test_set_history_for_wrong_key_ignored(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            await pilot.pause()
            # An out-of-date fetch for a previously-selected metric should
            # be silently dropped — toggles wouldn't apply to the wrong
            # series, status wouldn't update, etc.
            zoom.set_history(_history("acc", points=3))
            await pilot.pause()
            assert zoom._history is None

    async def test_set_history_redraws_status(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            zoom.set_history(_history("loss", points=4, subsampled=True))
            await pilot.pause()
            status = zoom.query_one("#metric-zoom-status", Static)
            text = str(status.render())
            assert "loss" in text
            assert "points: 4" in text
            assert "subsampled" in text
            assert "smoothing: off" in text
            assert "x: step" in text

    async def test_toggle_smoothing_emits_message(self) -> None:
        received: list[tuple[str, object]] = []

        class _CaptureApp(App[None]):
            def compose(self) -> ComposeResult:
                yield MetricZoomView(id="zoom")

            def on_metric_zoom_view_toggle_changed(
                self, event: MetricZoomView.ToggleChanged
            ) -> None:
                received.append((event.name, event.value))
                event.stop()

        async with _CaptureApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom", MetricZoomView)
            zoom.set_metric_key("loss")
            zoom.set_history(_history("loss", points=5))
            zoom.action_toggle_smoothing()
            zoom.action_toggle_log_scale()
            zoom.action_toggle_x_axis()
            for _ in range(3):
                await pilot.pause()
            names = [n for n, _ in received]
            assert names == ["smoothing", "log_scale", "x_axis"]
            assert received[0][1] is True
            assert received[1][1] is True
            assert received[2][1] == "wall_clock"

    async def test_series_for_plot_step_axis(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            history = _history("loss", points=4)
            zoom.set_history(history)
            xs, ys = zoom._series_for_plot(history.history)
            assert xs == [0.0, 1.0, 2.0, 3.0]
            assert ys == [0.0, 1.0, 2.0, 3.0]

    async def test_series_for_plot_wall_clock(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            history = _history("loss", points=3)
            zoom.set_history(history)
            zoom.action_toggle_x_axis()
            xs, ys = zoom._series_for_plot(history.history)
            # Wall-clock xs are elapsed seconds from the first point —
            # never raw epoch timestamps (unreadable as axis ticks).
            assert xs == [0.0, 1.0, 2.0]
            assert ys == [0.0, 1.0, 2.0]
            assert zoom._x_label() == "elapsed (s)"

    async def test_series_for_plot_wall_clock_scales_to_minutes(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            # Points 100 seconds apart: span 400s > 120s → minutes.
            history = ExperimentMetricHistory(
                experiment_id="exp",
                key="loss",
                subsampled=False,
                history=[
                    MetricPoint(
                        value=float(i),
                        step=i,
                        logged_at=datetime(
                            2026, 1, 1, 0, i, 40, tzinfo=UTC
                        ),
                    )
                    for i in range(5)
                ],
            )
            # 60s apart per point → 240s span → minutes unit.
            zoom.set_history(history)
            zoom.action_toggle_x_axis()
            xs, _ys = zoom._series_for_plot(history.history)
            assert xs == [0.0, 1.0, 2.0, 3.0, 4.0]
            assert zoom._x_label() == "elapsed (m)"

    async def test_series_for_plot_log_scale_filters_non_positive(
        self,
    ) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            # First point has value 0 — should be dropped under log Y.
            history = _history("loss", points=4)
            zoom.set_history(history)
            zoom.action_toggle_log_scale()
            xs, ys = zoom._series_for_plot(history.history)
            assert 0.0 not in ys
            assert xs == [1.0, 2.0, 3.0]
            assert ys == [1.0, 2.0, 3.0]

    async def test_series_for_plot_smoothing_changes_values(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            # Build a series with a big step so smoothing has something to do.
            history = ExperimentMetricHistory(
                experiment_id="exp",
                key="loss",
                subsampled=False,
                history=[
                    MetricPoint(value=0.0, step=0),
                    MetricPoint(value=10.0, step=1),
                    MetricPoint(value=10.0, step=2),
                ],
            )
            zoom.set_history(history)
            _, raw_ys = zoom._series_for_plot(history.history)
            zoom.action_toggle_smoothing()
            _, smoothed_ys = zoom._series_for_plot(history.history)
            # First value stays put; second value is dampened.
            assert raw_ys[0] == smoothed_ys[0]
            assert smoothed_ys[1] < raw_ys[1]


# ---------------------------------------------------------------------------
# Keymap integration: zoom + toggle commands are discoverable.
# ---------------------------------------------------------------------------


class TestKeymapRegistration:
    def test_zoom_actions_registered(self) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        for cmd_id in (
            "metrics.zoom",
            "metrics.toggle_smoothing",
            "metrics.toggle_log_scale",
            "metrics.toggle_x_axis",
        ):
            assert cmd_id in registry, f"{cmd_id} missing from keymap"

    def test_zoom_action_appears_in_palette_search(self) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        labels = {cmd.label for cmd in registry.all()}
        assert "Zoom" in labels
        assert "Smoothing" in labels
        assert "Log scale" in labels
        assert "X axis" in labels


# ---------------------------------------------------------------------------
# Arrow-key navigation between grid cells
# ---------------------------------------------------------------------------


class TestGridArrowNavigation:
    """Arrows (and h/j/k/l) move focus between cells in 2D.

    The harness terminal is 120 columns wide so the responsive layout
    settles on two columns; five metrics then wrap as::

        a b
        c d
        e
    """

    async def _grid_with_five(self, pilot) -> tuple[MetricGrid, dict[str, MetricCell]]:
        await pilot.pause()
        grid = pilot.app.query_one("#grid-under-test", MetricGrid)
        grid.set_metric_keys(["a", "b", "c", "d", "e"])
        await pilot.pause()
        assert grid._cols == 2
        cells = {c.metric_key: c for c in grid.query(MetricCell)}
        cells["a"].focus()
        await pilot.pause()
        return grid, cells

    async def test_arrows_move_focus_in_2d(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            _, cells = await self._grid_with_five(pilot)
            await pilot.press("right")
            await pilot.pause()
            assert pilot.app.focused is cells["b"]
            await pilot.press("down")
            await pilot.pause()
            assert pilot.app.focused is cells["d"]
            await pilot.press("left")
            await pilot.pause()
            assert pilot.app.focused is cells["c"]
            await pilot.press("up")
            await pilot.pause()
            assert pilot.app.focused is cells["a"]

    async def test_vim_keys_move_focus(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            _, cells = await self._grid_with_five(pilot)
            await pilot.press("l")
            await pilot.pause()
            assert pilot.app.focused is cells["b"]
            await pilot.press("j")
            await pilot.pause()
            assert pilot.app.focused is cells["d"]
            await pilot.press("h")
            await pilot.pause()
            assert pilot.app.focused is cells["c"]
            await pilot.press("k")
            await pilot.pause()
            assert pilot.app.focused is cells["a"]

    async def test_moves_clamp_at_edges(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            _, cells = await self._grid_with_five(pilot)
            # Left/up off the first cell stay put.
            await pilot.press("left")
            await pilot.press("up")
            await pilot.pause()
            assert pilot.app.focused is cells["a"]
            # Down off the last row stays put too.
            cells["e"].focus()
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert pilot.app.focused is cells["e"]

    async def test_down_into_partial_last_row_lands_on_last_cell(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            _, cells = await self._grid_with_five(pilot)
            # `d` sits above the hole in the partial last row; down
            # clamps to the final cell instead of dead-ending.
            cells["d"].focus()
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert pilot.app.focused is cells["e"]

    async def test_right_wraps_to_next_row_in_reading_order(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            _, cells = await self._grid_with_five(pilot)
            cells["b"].focus()
            await pilot.pause()
            await pilot.press("right")
            await pilot.pause()
            assert pilot.app.focused is cells["c"]

    async def test_focus_first_cell(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            grid, cells = await self._grid_with_five(pilot)
            cells["e"].focus()
            await pilot.pause()
            assert grid.focus_first_cell() is True
            await pilot.pause()
            assert pilot.app.focused is cells["a"]

    async def test_focus_first_cell_without_cells_focuses_grid(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            assert grid.focus_first_cell() is False
            await pilot.pause()
            assert pilot.app.focused is grid


# ---------------------------------------------------------------------------
# Zoom view: ←/→ metric stepping and toggle preservation
# ---------------------------------------------------------------------------


class TestZoomMetricStepping:
    async def test_arrows_post_step_requests(self) -> None:
        received: list[int] = []

        class _CaptureApp(App[None]):
            def compose(self) -> ComposeResult:
                yield MetricZoomView(id="zoom")

            def on_metric_zoom_view_step_requested(
                self, event: MetricZoomView.StepRequested
            ) -> None:
                received.append(event.delta)
                event.stop()

        async with _CaptureApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom", MetricZoomView)
            zoom.focus()
            await pilot.pause()
            await pilot.press("right", "left", "l", "h")
            await pilot.pause()
            assert received == [1, -1, 1, -1]

    async def test_set_metric_key_can_preserve_toggles(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            zoom.action_toggle_smoothing()
            zoom.action_toggle_log_scale()
            await pilot.pause()
            zoom.set_metric_key("acc", preserve_toggles=True)
            assert zoom.smoothing is True
            assert zoom.log_scale is True
            # The default path still resets, so a fresh zoom opens clean.
            zoom.set_metric_key("f1")
            assert zoom.smoothing is False
            assert zoom.log_scale is False


# ---------------------------------------------------------------------------
# Smoke: the screen-style focus contract works through PanelFrame.
# ---------------------------------------------------------------------------


class TestCellFocusable:
    async def test_cells_are_focusable(self) -> None:
        async with _GridApp().run_test() as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            grid.set_metric_keys(["loss"])
            await pilot.pause()
            cell = grid.query_one(MetricCell)
            assert cell.can_focus is True
            cell.focus()
            await pilot.pause()
            assert cell.has_focus is True
