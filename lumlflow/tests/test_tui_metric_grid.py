"""Unit tests for the metric grid + zoom widgets.

These tests focus on the widgets themselves, in isolation from the
experiment-detail screen — the integration with the screen
(`refresh_live`, message routing, keymap binding) is covered by
``tests/test_tui_experiment_detail.py``. Here we verify the
presentational contract: grid cells map to keys, history flows into
the right cell, empty states render, and the zoom view renders the
selected metric.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from lumlflow.schemas.experiments import ExperimentMetricHistory, MetricPoint
from lumlflow.tui.widgets.metric_grid import (
    MetricCell,
    MetricGrid,
    MetricZoomView,
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

    async def test_set_history_for_wrong_key_ignored(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            await pilot.pause()
            # An out-of-date fetch for a previously-selected metric is
            # silently dropped so it never renders as the wrong series.
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


# ---------------------------------------------------------------------------
# No redundant re-renders
# ---------------------------------------------------------------------------


class TestNoRedundantRerender:
    async def test_history_requested_once_at_rendered_width(self) -> None:
        """Regression: cells used to request history at mount time with
        width 0 (fallback max_points), then the refresh tick re-fetched
        at the real width — every chart visibly re-rendered at a
        different granularity. The request must fire once, after
        layout, with a width-quantized max_points."""

        received: list[tuple[str, int]] = []

        class _CaptureApp(App[None]):
            def compose(self) -> ComposeResult:
                yield MetricGrid(id="grid")

            def on_metric_grid_history_needed(
                self, event: MetricGrid.HistoryNeeded
            ) -> None:
                received.append((event.metric_key, event.max_points))
                event.stop()

        async with _CaptureApp().run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid", MetricGrid)
            grid.set_metric_keys(["loss"])
            for _ in range(5):
                await pilot.pause()
            assert len(received) == 1
            _, max_points = received[0]
            # Quantized and sized from the real (laid out) width.
            assert max_points % 50 == 0
            cell = grid.query_one(MetricCell)
            assert cell.chart_max_points() == max_points

    async def test_set_history_skips_redraw_when_unchanged(self) -> None:
        async with _GridApp().run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            grid = pilot.app.query_one("#grid-under-test", MetricGrid)
            grid.set_metric_keys(["loss"])
            for _ in range(3):
                await pilot.pause()
            cell = grid.query_one(MetricCell)
            cell.set_history(_history("loss", points=5))
            redraws: list[int] = []
            cell._redraw = lambda: redraws.append(1)  # type: ignore[method-assign]
            cell.set_history(_history("loss", points=5))
            assert redraws == []
            cell.set_history(_history("loss", points=6))
            assert redraws == [1]

    async def test_zoom_set_history_skips_redraw_when_unchanged(self) -> None:
        async with _ZoomApp().run_test() as pilot:
            await pilot.pause()
            zoom = pilot.app.query_one("#zoom-under-test", MetricZoomView)
            zoom.set_metric_key("loss")
            zoom.set_history(_history("loss", points=5))
            redraws: list[int] = []
            zoom._redraw = lambda: redraws.append(1)  # type: ignore[method-assign]
            zoom.set_history(_history("loss", points=5))
            assert redraws == []
            zoom.set_history(_history("loss", points=6))
            assert redraws == [1]


# ---------------------------------------------------------------------------
# Keymap integration: the zoom command is discoverable.
# ---------------------------------------------------------------------------


class TestKeymapRegistration:
    def test_zoom_action_registered(self) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        assert "metrics.zoom" in registry

    def test_zoom_action_appears_in_palette_search(self) -> None:
        from lumlflow.tui.keymap import build_default_registry

        registry = build_default_registry()
        labels = {cmd.label for cmd in registry.all()}
        assert "Zoom" in labels


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
