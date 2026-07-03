"""Small-multiples metric grid and zoom view.

The Metrics tab of the experiment detail screen renders one mini-chart
per metric key in a responsive, scrollable grid (the ``MetricGrid``
widget below). Pressing Enter on a focused mini-chart opens the
``MetricZoomView``: a single large chart for that metric.

The widgets are presentational — they own no facade and no fetching.
The parent screen calls ``set_metric_keys`` to seed the grid and
``set_metric_history`` to push points (per metric for the grid, for
the single focused metric for the zoom view). This keeps the worker /
result lifecycle on the screen and lets the widgets stay easy to test
in isolation.
"""

from __future__ import annotations

from collections.abc import Iterable

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import Grid, Vertical, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual_plotext import PlotextPlot

from lumlflow.schemas.experiments import ExperimentMetricHistory, MetricPoint
from lumlflow.tui.widgets.panel_frame import PanelFrame

_DEFAULT_FALLBACK_WIDTH = 40

# Layout constants for the small-multiples grid. The cell height is fixed
# so every mini-chart has room for the plot body plus its axis labels
# (a taller cell than before — the old 10-row cells cropped the x-axis
# ticks). Columns are chosen responsively from the available width so the
# charts never get squeezed below a legible width.
_CELL_HEIGHT = 13
_GRID_GUTTER = 1
_MIN_CELL_WIDTH = 46
_MAX_COLS = 3


def _sanitize_metric_key(key: str) -> str:
    """Return a CSS-safe id slug for a metric key."""

    return "".join(c if c.isalnum() or c in "-_" else "_" for c in key)


def _same_series(
    a: ExperimentMetricHistory, b: ExperimentMetricHistory
) -> bool:
    """True when two histories plot identically (steps and values)."""

    if a.key != b.key or a.subsampled != b.subsampled:
        return False
    if len(a.history) != len(b.history):
        return False
    return all(
        pa.step == pb.step and pa.value == pb.value
        for pa, pb in zip(a.history, b.history, strict=True)
    )


class MetricCell(PanelFrame):
    """A single framed mini-chart in the metric grid.

    The cell wraps a ``PlotextPlot`` and exposes the metric key so the
    grid can dispatch zoom requests / history updates by key. Focusing
    a cell highlights its border via the inherited ``PanelFrame`` focus
    contract; pressing Enter posts ``MetricCell.ZoomRequested`` which
    the grid translates into a ``MetricGrid.ZoomRequested`` message
    that the screen acts on.
    """

    DEFAULT_CSS = """
    MetricCell {
        height: 13;
        width: 1fr;
    }
    MetricCell:focus {
        /* PanelFrame.-focused already styles the border; we also keep
         * the cell scrollable to capture focus so the cursor visually
         * sits on the cell. */
    }
    MetricCell .metric-cell-chart {
        height: 1fr;
    }
    MetricCell .metric-cell-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $foreground 60%;
    }
    """

    can_focus = True

    BINDINGS = [
        Binding("enter", "zoom", "Zoom", show=False),
        # Arrow keys (plus vim h/j/k/l) move between cells; the grid
        # resolves the 2D target from its current column count.
        Binding("up,k", "grid_move('up')", "Up", show=False),
        Binding("down,j", "grid_move('down')", "Down", show=False),
        Binding("left,h", "grid_move('left')", "Left", show=False),
        Binding("right,l", "grid_move('right')", "Right", show=False),
    ]

    class ZoomRequested(Message):
        """Posted when the user presses Enter on a focused mini-chart."""

        def __init__(self, metric_key: str) -> None:
            super().__init__()
            self.metric_key = metric_key

    class MoveRequested(Message):
        """Posted when the user presses an arrow key on a focused cell."""

        def __init__(self, metric_key: str, direction: str) -> None:
            super().__init__()
            self.metric_key = metric_key
            self.direction = direction

    def __init__(
        self,
        metric_key: str,
        *,
        id: str | None = None,
    ) -> None:
        cell_id = id or f"metric-cell-{_sanitize_metric_key(metric_key)}"
        super().__init__(title=metric_key, id=cell_id)
        self.metric_key = metric_key
        self._history: ExperimentMetricHistory | None = None
        self._last_render_width: int = 0
        self._history_requested: bool = False

    def compose(self) -> Iterable[Widget]:  # type: ignore[override]
        yield PlotextPlot(classes="metric-cell-chart")
        yield Static("(no points yet)", classes="metric-cell-empty")

    def on_mount(self) -> None:
        super().on_mount()
        self._sync_empty_state()

    def on_resize(self) -> None:
        # Cells mount at width 0 (and stay 0 while their tab is hidden),
        # so the history request waits for the first real layout — a
        # fetch sized to the fallback width would be re-fetched at the
        # real width on the next refresh tick, visibly re-rendering the
        # chart at a different granularity.
        if self._history_requested or self._history is not None:
            return
        if self.size.width <= 0:
            return
        self._history_requested = True
        self.post_message(
            MetricGrid.HistoryNeeded(self.metric_key, self.chart_max_points())
        )

    def chart_max_points(self) -> int:
        """Estimate how many points to subsample to for this cell."""

        try:
            chart = self.query_one(PlotextPlot)
        except Exception:
            return max(40, _DEFAULT_FALLBACK_WIDTH * 2)
        # The chart child can lag the cell by one layout pass, so fall
        # back to the cell's own width minus the frame borders.
        width = (
            chart.size.width
            or chart.virtual_size.width
            or max(0, self.size.width - 2)
            or _DEFAULT_FALLBACK_WIDTH
        )
        self._last_render_width = width
        # Two points per terminal column: smooth enough without
        # overshooting the renderer's resolution. Quantized upward to a
        # multiple of 50 — width can differ by a column or two between
        # measurements (chart vs cell, layout passes), and a slightly
        # different max_points would refetch and repaint a chart that
        # looks identical.
        raw = max(40, int(width) * 2)
        return -(-raw // 50) * 50

    def set_history(self, history: ExperimentMetricHistory) -> None:
        """Push new points into the cell and redraw.

        Skips the redraw when the series is unchanged — live refresh
        re-fetches on a timer, and repainting an identical chart makes
        it visibly churn for no reason.
        """

        if self._history is not None and _same_series(self._history, history):
            return
        self._history = history
        self._redraw()

    def _redraw(self) -> None:
        self._sync_empty_state()
        history = self._history
        if history is None or not history.history:
            return
        try:
            chart = self.query_one(PlotextPlot)
        except Exception:
            return
        plt = chart.plt
        plt.clear_figure()
        plt.clear_data()
        plt.clear_color()
        steps = [p.step for p in history.history]
        values = [p.value for p in history.history]
        plt.plot(steps, values, marker="braille")
        # Skip the title — the panel frame's border title already
        # carries the metric name and a chart title would steal a row.
        chart.refresh()

    def _sync_empty_state(self) -> None:
        try:
            chart = self.query_one(PlotextPlot)
            empty = self.query_one(".metric-cell-empty", Static)
        except Exception:
            return
        has_points = (
            self._history is not None and bool(self._history.history)
        )
        chart.display = has_points
        empty.display = not has_points

    # ----- Enter to zoom -----

    def action_zoom(self) -> None:
        self.post_message(self.ZoomRequested(self.metric_key))

    def action_grid_move(self, direction: str) -> None:
        self.post_message(self.MoveRequested(self.metric_key, direction))

    def on_click(self, _: events.Click) -> None:
        # A click also opens the zoom view — match mouse and keyboard.
        self.focus()
        self.post_message(self.ZoomRequested(self.metric_key))


class MetricGrid(VerticalScroll):
    """Responsive scrollable grid of metric mini-charts.

    The grid lays out one ``MetricCell`` per metric key in a CSS Grid
    that wraps to two columns by default (collapsing to one column on
    narrow terminals via the screen's own CSS). The widget owns no
    fetching: ``set_metric_keys`` builds the cells, ``apply_history``
    routes a fetched history to the right cell.
    """

    DEFAULT_CSS = """
    MetricGrid {
        layout: vertical;
    }
    MetricGrid #metric-grid-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $foreground 60%;
    }
    MetricGrid #metric-grid-empty.-hidden {
        display: none;
    }
    MetricGrid #metric-grid-cells {
        grid-size: 2;
        grid-gutter: 1;
        grid-rows: 13;
        height: auto;
    }
    MetricGrid #metric-grid-cells.-hidden {
        display: none;
    }
    """

    class ZoomRequested(Message):
        """Bubbled from a cell when the user wants to zoom in."""

        def __init__(self, metric_key: str) -> None:
            super().__init__()
            self.metric_key = metric_key

    class HistoryNeeded(Message):
        """Posted when a cell needs its history fetched.

        Sent by a cell on its first real layout (so ``max_points``
        matches the rendered width) and by ``request_refresh_visible``.
        The screen owns the facade and the worker; the widget just
        announces "I have a cell for ``metric_key`` with viewport
        ``max_points``; please go fetch."
        """

        def __init__(self, metric_key: str, max_points: int) -> None:
            super().__init__()
            self.metric_key = metric_key
            self.max_points = max_points

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._metric_keys: list[str] = []
        self._cells: dict[str, MetricCell] = {}
        # Responsive column count, kept in sync by `_relayout` so arrow
        # navigation resolves up/down targets against the real layout.
        self._cols: int = 2

    def compose(self) -> Iterable[Widget]:  # type: ignore[override]
        yield Static(
            "No metrics logged for this experiment yet.",
            id="metric-grid-empty",
        )
        yield Grid(id="metric-grid-cells")

    def on_mount(self) -> None:
        self._sync_empty_state()

    def on_resize(self) -> None:
        # Column count and total grid height depend on the viewport
        # width, so recompute the layout whenever the grid is resized.
        self._relayout()

    def _relayout(self) -> None:
        """Size the cell grid to the number of metrics and the viewport.

        The inner ``Grid`` cannot compute its own height from wrapped
        auto rows (Textual collapses it to a single row), which used to
        clip every chart past the first row. We pick a responsive column
        count from the available width and set an explicit grid height so
        the enclosing ``VerticalScroll`` can scroll the full set.
        """

        n = len(self._metric_keys)
        if n == 0:
            return
        try:
            grid = self.query_one("#metric-grid-cells", Grid)
        except Exception:
            return
        width = self.size.width or self.container_size.width
        if width <= 0:
            width = _MIN_CELL_WIDTH * 2
        cols = max(1, min(_MAX_COLS, n, width // _MIN_CELL_WIDTH))
        rows = -(-n // cols)  # ceil division
        self._cols = cols
        grid.styles.grid_size_columns = cols
        grid.styles.height = rows * (_CELL_HEIGHT + _GRID_GUTTER)

    @property
    def metric_keys(self) -> tuple[str, ...]:
        return tuple(self._metric_keys)

    @property
    def cells(self) -> dict[str, MetricCell]:
        return dict(self._cells)

    def set_metric_keys(self, keys: Iterable[str]) -> None:
        """Replace the set of mini-charts to match ``keys``.

        Cells for removed keys are dropped, kept cells are reused
        (preserving their cached history + chart contents), and new
        cells are mounted with a ``HistoryNeeded`` request so the
        screen can issue a fetch.
        """

        new_keys = list(keys)
        keep = set(new_keys)

        # Drop cells that are no longer in the set.
        try:
            grid = self.query_one("#metric-grid-cells", Grid)
        except Exception:
            return
        for key in list(self._cells.keys()):
            if key not in keep:
                cell = self._cells.pop(key)
                try:
                    cell.remove()
                except Exception:
                    pass

        # Add cells in the order requested. Mount any new ones, leave
        # existing ones where they are so the user's cursor stays put.
        for key in new_keys:
            if key in self._cells:
                continue
            cell = MetricCell(key)
            self._cells[key] = cell
            grid.mount(cell)

        self._metric_keys = new_keys
        self._sync_empty_state()
        self._relayout()
        # No fetch requests here: each cell announces its own
        # ``HistoryNeeded`` from ``on_resize`` once it has a real width,
        # so ``max_points`` always matches the rendered size.

    def apply_history(self, history: ExperimentMetricHistory) -> None:
        """Push fetched points into the cell for ``history.key``."""

        cell = self._cells.get(history.key)
        if cell is None:
            return
        cell.set_history(history)

    def visible_metric_keys(self) -> tuple[str, ...]:
        """Return the keys currently rendered in the grid."""

        return tuple(self._metric_keys)

    def request_refresh_visible(self) -> None:
        """Re-request history for every visible cell.

        Called by the screen on live-refresh / resize so existing
        cells keep their cached history but get repainted with the
        latest points.
        """

        for key, cell in self._cells.items():
            max_points = cell.chart_max_points()
            self.post_message(self.HistoryNeeded(key, max_points))

    def _sync_empty_state(self) -> None:
        try:
            empty = self.query_one("#metric-grid-empty", Static)
            grid = self.query_one("#metric-grid-cells", Grid)
        except Exception:
            return
        has_keys = bool(self._metric_keys)
        if has_keys:
            empty.add_class("-hidden")
            grid.remove_class("-hidden")
        else:
            empty.remove_class("-hidden")
            grid.add_class("-hidden")

    # ----- Cell zoom request bubble-up -----

    def on_metric_cell_zoom_requested(
        self, event: MetricCell.ZoomRequested
    ) -> None:
        """Re-emit a cell zoom request at the grid level."""

        event.stop()
        self.post_message(self.ZoomRequested(event.metric_key))

    # ----- Arrow-key navigation between cells -----

    def on_metric_cell_move_requested(
        self, event: MetricCell.MoveRequested
    ) -> None:
        event.stop()
        self.focus_neighbor(event.metric_key, event.direction)

    def focus_neighbor(self, metric_key: str, direction: str) -> None:
        """Focus the cell adjacent to ``metric_key`` in ``direction``.

        Left/right walk the cells in reading order (wrapping across row
        boundaries); up/down move by the current column count. Moves off
        the first/last cell are clamped, except down from the last full
        row which lands on the final cell of a partial last row.
        """

        keys = self._metric_keys
        if metric_key not in keys:
            return
        index = keys.index(metric_key)
        n = len(keys)
        cols = max(1, self._cols)
        if direction == "left":
            target = index - 1
        elif direction == "right":
            target = index + 1
        elif direction == "up":
            target = index - cols
        elif direction == "down":
            target = index + cols
            if target >= n and index // cols < (n - 1) // cols:
                target = n - 1
        else:
            return
        if not (0 <= target < n) or target == index:
            return
        self.focus_cell(keys[target])

    def focus_cell(self, metric_key: str) -> bool:
        """Focus the cell for ``metric_key``; returns True on success."""

        cell = self._cells.get(metric_key)
        if cell is None:
            return False
        cell.focus()
        cell.scroll_visible()
        return True

    def focus_first_cell(self) -> bool:
        """Focus the first cell, falling back to the grid body itself."""

        for key in self._metric_keys:
            if self.focus_cell(key):
                return True
        self.focus()
        return False


class MetricZoomView(Vertical):
    """Large single-metric chart.

    Like ``MetricGrid``, the view is presentational. The screen pushes
    a metric key (``set_metric_key``) and the latest history
    (``set_history``); the view redraws on each change.
    """

    DEFAULT_CSS = """
    MetricZoomView {
        layout: vertical;
        height: 1fr;
    }
    MetricZoomView #metric-zoom-panel {
        height: 1fr;
    }
    MetricZoomView #metric-zoom-chart {
        height: 1fr;
    }
    MetricZoomView #metric-zoom-status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    MetricZoomView #metric-zoom-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $foreground 60%;
    }
    MetricZoomView #metric-zoom-chart.-hidden,
    MetricZoomView #metric-zoom-empty.-hidden {
        display: none;
    }
    """

    BINDINGS = [
        # Step between metrics without leaving the zoom view — the same
        # arrows that move between cells on the grid.
        Binding("left,h", "step_metric(-1)", "Prev metric", show=False),
        Binding("right,l", "step_metric(1)", "Next metric", show=False),
    ]

    can_focus = True

    class StepRequested(Message):
        """Posted when the user steps to the previous/next metric."""

        def __init__(self, delta: int) -> None:
            super().__init__()
            self.delta = delta

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._metric_key: str | None = None
        self._history: ExperimentMetricHistory | None = None

    def compose(self) -> Iterable[Widget]:  # type: ignore[override]
        with PanelFrame(
            title="(no metric)",
            fill=True,
            id="metric-zoom-panel",
        ):
            yield PlotextPlot(id="metric-zoom-chart")
            yield Static(
                "(no points yet)",
                id="metric-zoom-empty",
            )
            yield Static("", id="metric-zoom-status")

    def on_mount(self) -> None:
        self._sync_panel_title()

    # ----- public state -----

    @property
    def metric_key(self) -> str | None:
        return self._metric_key

    def set_metric_key(self, key: str | None) -> None:
        if key == self._metric_key:
            return
        self._metric_key = key
        self._history = None
        self._sync_panel_title()
        self._redraw()

    def set_history(self, history: ExperimentMetricHistory) -> None:
        """Push new points and redraw (skipped when unchanged)."""

        if self._metric_key is None or history.key != self._metric_key:
            # Stale fetch for a different metric — ignore.
            return
        if self._history is not None and _same_series(self._history, history):
            return
        self._history = history
        self._redraw()

    def action_step_metric(self, delta: int) -> None:
        self.post_message(self.StepRequested(delta))

    # ----- redraw -----

    def _redraw(self) -> None:
        try:
            chart = self.query_one("#metric-zoom-chart", PlotextPlot)
            empty = self.query_one("#metric-zoom-empty", Static)
        except Exception:
            return
        history = self._history
        if history is None or not history.history:
            chart.add_class("-hidden")
            empty.remove_class("-hidden")
            self._update_status()
            return
        chart.remove_class("-hidden")
        empty.add_class("-hidden")
        xs, ys = self._series_for_plot(history.history)
        plt = chart.plt
        plt.clear_figure()
        plt.clear_data()
        plt.clear_color()
        if xs and ys:
            plt.plot(xs, ys, marker="braille")
            plt.title(history.key)
            plt.xlabel("step")
            plt.ylabel(history.key)
        chart.refresh()
        self._update_status()

    def _series_for_plot(
        self, points: list[MetricPoint]
    ) -> tuple[list[float], list[float]]:
        return [float(p.step) for p in points], [p.value for p in points]

    def _sync_panel_title(self) -> None:
        try:
            panel = self.query_one("#metric-zoom-panel", PanelFrame)
        except Exception:
            return
        panel.set_title(self._metric_key or "(no metric)")

    def _update_status(self) -> None:
        try:
            status = self.query_one("#metric-zoom-status", Static)
        except Exception:
            return
        history = self._history
        if history is None:
            status.update(Text("(no metric selected)", style="dim"))
            return
        if not history.history:
            status.update(Text("(no points yet)", style="dim"))
            return
        bits = [
            f"metric: {history.key}",
            f"points: {len(history.history)}",
        ]
        if history.subsampled:
            bits.append("subsampled")
        status.update("  ·  ".join(bits))


__all__ = (
    "MetricCell",
    "MetricGrid",
    "MetricZoomView",
    "_sanitize_metric_key",
)
