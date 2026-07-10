"""Comparison screen for a selected set of experiments.

SPEC: "the user selects a set of experiments (multi-select from an
experiments screen, or assembled across groups) and opens the
comparison screen. It shows: a static-parameter diff table with
differing rows highlighted; an overlaid metric chart plotting the same
dynamic metric across the selected experiments (multi-series); and an
eval score comparison keyed by dataset. This reuses the batch/group
experiment and metric-history reads the handlers already provide;
aggregation/diffing of the returned schemas happens in the TUI."

The screen is composed of three stacked sections — each section pulls
its data on a worker thread via the `DataFacade` (the event loop never
blocks). The selection is provided as a list of `ExperimentDetails`
captured at the moment the user pressed `c`; no extra round-trip is
needed for the static-params table or the metric-key chooser.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, ListItem, ListView, Static
from textual_plotext import PlotextPlot

from lumlflow.schemas.experiments import (
    ExperimentDetails,
    ExperimentMetricHistory,
    ExperimentStatus,
)
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment, PanelFrame

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp


# Stable palette of series colours for the overlaid metric chart and the
# experiment-column headers in the diff table. Two lists run in lockstep
# because rich Text uses ANSI/CSS names while plotext expects its own
# colour vocabulary — `_RICH_SERIES_COLORS[i]` and `_PLOT_SERIES_COLORS[i]`
# are the same logical colour for experiment `i`.
_RICH_SERIES_COLORS: tuple[str, ...] = (
    "cyan",
    "magenta",
    "green",
    "yellow",
    "blue",
    "red",
    "bright_cyan",
    "bright_magenta",
)
_PLOT_SERIES_COLORS: tuple[str, ...] = (
    "cyan",
    "magenta",
    "green",
    "orange",
    "blue",
    "red",
    "cyan+",
    "magenta+",
)


def _rich_color_for(index: int) -> str:
    return _RICH_SERIES_COLORS[index % len(_RICH_SERIES_COLORS)]


def _plot_color_for(index: int) -> str:
    return _PLOT_SERIES_COLORS[index % len(_PLOT_SERIES_COLORS)]


_STATUS_PLAIN_STYLE: dict[ExperimentStatus, str] = {
    ExperimentStatus.ACTIVE: "bold cyan",
    ExperimentStatus.COMPLETED: "bold green",
    ExperimentStatus.ERROR: "bold red",
}


@dataclass(frozen=True)
class _ParamDiffRow:
    """One row in the static-param diff table."""

    key: str
    values: list[str]
    differs: bool


def _stringify(value: Any) -> str:
    """Format a param value for the diff table.

    Keeps the rendering deterministic across types — primitives become
    their `repr`, dicts/lists become a stable JSON-ish string. `None`
    rendering uses the em dash so missing keys read at a glance.
    """

    if value is None:
        return "—"
    if isinstance(value, bool | int | float | str):
        return str(value)
    return repr(value)


def _diff_static_params(
    experiments: list[ExperimentDetails],
) -> list[_ParamDiffRow]:
    """Build the param-diff rows across the selected experiments.

    The keys are the union of every experiment's `static_params`. For
    each key the row carries the per-experiment value (or `None` if
    missing) and a `differs` flag (`True` iff at least two values differ).
    """

    keys: set[str] = set()
    for exp in experiments:
        if exp.static_params:
            keys.update(exp.static_params.keys())
    rows: list[_ParamDiffRow] = []
    for key in sorted(keys):
        raw_values = [
            (exp.static_params or {}).get(key) for exp in experiments
        ]
        differs = len({_stringify(v) for v in raw_values}) > 1
        rows.append(
            _ParamDiffRow(
                key=key,
                values=[_stringify(v) for v in raw_values],
                differs=differs,
            )
        )
    return rows


def _shared_metric_keys(experiments: list[ExperimentDetails]) -> list[str]:
    """Return the metric keys present in at least one selected experiment.

    Per SPEC the overlay plots the same metric across experiments — we
    show every key that appears in ≥1 experiment so the user can pick;
    series for experiments missing that key are simply omitted from the
    plot. Sorted for deterministic ordering in the chooser.
    """

    keys: set[str] = set()
    for exp in experiments:
        if exp.dynamic_params:
            keys.update(exp.dynamic_params.keys())
    return sorted(keys)


def _metric_list_item_id(key: str) -> str:
    """Build a CSS-safe `ListItem` id for a metric key.

    Metric keys may contain `/`, `.`, etc. that Textual rejects in
    widget ids; sanitize before hand-off to the ListView.
    """

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    return f"cmp-metric-item-{safe}"


class ComparisonScreen(BaseScreen):
    """Side-by-side comparison of a selected set of experiments.

    Three stacked panels:

    - **Static-param diff** — table with one row per key (union across
      the selection), one column per experiment; rows that disagree are
      highlighted with the diff colour.
    - **Metric overlay** — a metric chooser (left) plus an overlaid
      line chart (right) drawing one series per experiment for the
      chosen metric. Series are subsampled to the chart's rendered
      width.
    - **Eval scores by dataset** — a table of avg scores per dataset,
      one row per dataset, one block of columns per experiment.

    All data fetches run on Textual worker threads via the facade so
    the event loop is never blocked.
    """

    DEFAULT_CSS = """
    ComparisonScreen {
        layout: vertical;
    }
    ComparisonScreen #cmp-body {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    ComparisonScreen .cmp-card {
        height: auto;
        margin-bottom: 1;
    }
    ComparisonScreen #cmp-summary {
        height: auto;
    }
    ComparisonScreen #cmp-legend {
        height: auto;
        padding: 0 1;
    }
    ComparisonScreen #cmp-params-table {
        height: auto;
        max-height: 14;
    }
    ComparisonScreen #cmp-metric-card {
        height: 1fr;
    }
    ComparisonScreen #cmp-metric-row {
        height: 1fr;
        layout: horizontal;
    }
    ComparisonScreen #cmp-metric-list {
        width: 24;
        border-right: solid $panel;
    }
    ComparisonScreen #cmp-metric-right {
        width: 1fr;
        layout: vertical;
    }
    ComparisonScreen #cmp-metric-status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    ComparisonScreen #cmp-metric-chart {
        height: 1fr;
    }
    ComparisonScreen #cmp-evals-table {
        height: auto;
        max-height: 12;
    }
    ComparisonScreen .empty-panel {
        padding: 1 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("j", "body_scroll_down", "Down", show=False),
        Binding("k", "body_scroll_up", "Up", show=False),
        Binding("g", "body_scroll_home", "Top", show=False),
        Binding("G", "body_scroll_end", "Bottom", show=False),
        Binding("ctrl+d", "body_half_page_down", "Half-page down", show=False),
        Binding("ctrl+u", "body_half_page_up", "Half-page up", show=False),
    ]

    def __init__(
        self,
        *,
        facade: DataFacade | None,
        experiments: list[ExperimentDetails],
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        if len(experiments) < 2:
            raise ValueError(
                "ComparisonScreen requires at least 2 experiments"
            )
        self._facade = facade
        self._experiments = experiments
        self._metric_keys = _shared_metric_keys(experiments)
        self._selected_metric: str | None = (
            self._metric_keys[0] if self._metric_keys else None
        )
        # Per-experiment metric history; populated by the chart fetch.
        self._metric_histories: dict[str, ExperimentMetricHistory | None] = {}
        # Per-experiment dataset → avg-scores map; populated by the
        # eval section's lazy fetch on mount.
        self._eval_scores: dict[str, dict[str, dict[str, float]]] = {}
        self._dataset_ids: dict[str, list[str]] = {}
        self._last_chart_width: int = 0

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        # A scrollable body: on short terminals the stacked cards used
        # to clip silently inside a plain Container — now they scroll,
        # and the j/k/g/G bindings below have a real target.
        with VerticalScroll(id="cmp-body"):
            # Summary card — the legend lives here too, mapping each
            # experiment name to the color used in the metric overlay
            # series and the diff-table column headers. Keeping the
            # legend and summary in one frame ties the colors to the
            # set being compared.
            with PanelFrame(
                title=f"Comparing {len(self._experiments)} experiments",
                classes="cmp-card",
                id="cmp-summary-card",
            ):
                yield Static(self._summary_text(), id="cmp-summary")
                yield Static(self._legend_text(), id="cmp-legend")
            with PanelFrame(
                title="Static parameters",
                classes="cmp-card",
                id="cmp-params-card",
            ):
                yield DataTable(
                    id="cmp-params-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )
            with PanelFrame(
                title="Metric overlay",
                classes="cmp-card",
                id="cmp-metric-card",
            ):
                with Horizontal(id="cmp-metric-row"):
                    yield ListView(id="cmp-metric-list")
                    with Vertical(id="cmp-metric-right"):
                        yield Static("", id="cmp-metric-status")
                        yield PlotextPlot(id="cmp-metric-chart")
            with PanelFrame(
                title="Eval scores",
                classes="cmp-card",
                id="cmp-evals-card",
            ):
                yield DataTable(
                    id="cmp-evals-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )

    def on_mount(self) -> None:
        self._populate_params_table()
        self._populate_metric_chooser()
        self._populate_evals_table_header()
        # Kick off the single async loader that fetches metric series
        # and eval scores in sequence. Sequencing matters: each fetch
        # routes through the same SQLite meta DB connection, so two
        # threads issuing concurrent cursors against it can collide
        # with "bad parameter or other API misuse". Funneling both
        # data loads through one worker keeps the cursor usage strictly
        # serial without giving up the off-loop responsiveness.
        if self._selected_metric is not None or self._experiments:
            self._load_all_data()

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        return (
            BreadcrumbSegment("Groups"),
            BreadcrumbSegment(f"Compare ({len(self._experiments)})"),
        )

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global",)

    # ----- body scrolling -----

    def _scroll_body(self) -> VerticalScroll | None:
        try:
            return self.query_one("#cmp-body", VerticalScroll)
        except Exception:
            return None

    def action_body_scroll_down(self) -> None:
        body = self._scroll_body()
        if body is not None:
            body.scroll_relative(y=1, animate=False)

    def action_body_scroll_up(self) -> None:
        body = self._scroll_body()
        if body is not None:
            body.scroll_relative(y=-1, animate=False)

    def action_body_scroll_home(self) -> None:
        body = self._scroll_body()
        if body is not None:
            body.scroll_home(animate=False)

    def action_body_scroll_end(self) -> None:
        body = self._scroll_body()
        if body is not None:
            body.scroll_end(animate=False)

    def action_body_half_page_down(self) -> None:
        body = self._scroll_body()
        if body is not None:
            body.scroll_relative(
                y=max(1, body.size.height // 2), animate=False
            )

    def action_body_half_page_up(self) -> None:
        body = self._scroll_body()
        if body is not None:
            body.scroll_relative(
                y=-max(1, body.size.height // 2), animate=False
            )

    # ----- facade -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        return getattr(self.app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- summary header -----

    def _summary_text(self) -> Text:
        """Plain one-line summary of the set being compared.

        The colored legend lives in ``_legend_text`` so the panel can
        render both in distinct rows without one shadowing the other.
        """

        text = Text()
        text.append("Comparing ", style="dim")
        text.append(str(len(self._experiments)), style="bold")
        text.append(" experiments", style="dim")
        return text

    def _legend_text(self) -> Text:
        """Colored legend mapping each experiment name to its series color.

        Same color index is used by the metric overlay's plot series and
        the static-param diff table's per-experiment column header, so
        the legend is the single anchor that ties the colors together
        across the three sections.
        """

        text = Text()
        for i, exp in enumerate(self._experiments):
            color = _rich_color_for(i)
            if i > 0:
                text.append("  ")
            text.append("●", style=color)
            text.append(" ")
            text.append(exp.name, style=f"bold {color}")
            status_style = _STATUS_PLAIN_STYLE.get(exp.status, "dim")
            text.append(" ")
            text.append(exp.status.value, style=status_style)
            if exp.group_name:
                text.append(" ")
                text.append(f"({exp.group_name})", style="dim")
        return text

    # ----- static params diff -----

    def _populate_params_table(self) -> None:
        table = self.query_one("#cmp-params-table", DataTable)
        table.clear(columns=True)
        # Add per-experiment columns; the first column is the param key.
        table.add_column("Param", key="cmp-param-key")
        for i, exp in enumerate(self._experiments):
            label = Text(exp.name, style=f"bold {_rich_color_for(i)}")
            table.add_column(label, key=f"cmp-exp-{exp.id}")
        rows = _diff_static_params(self._experiments)
        self._param_rows = rows
        if not rows:
            table.add_row(
                Text("(no static params on any experiment)", style="dim"),
                *[Text("", style="dim") for _ in self._experiments],
                key="cmp-empty",
            )
            return
        for row in rows:
            self._add_param_row(table, row)

    def _add_param_row(self, table: DataTable, row: _ParamDiffRow) -> None:
        # Differing rows get the diff colour on the key cell so the eye
        # is drawn to the disagreement without colouring every value.
        if row.differs:
            key_cell = Text(row.key, style="bold $diff-changed")
        else:
            key_cell = Text(row.key)
        cells: list[Text] = [key_cell]
        for value in row.values:
            cell = Text(value)
            if row.differs:
                cell.stylize("$diff-changed")
            cells.append(cell)
        table.add_row(*cells, key=f"cmp-param-{row.key}")

    # ----- metric overlay -----

    def _populate_metric_chooser(self) -> None:
        view = self.query_one("#cmp-metric-list", ListView)
        view.clear()
        if not self._metric_keys:
            view.append(
                ListItem(
                    Static("(no metrics)"), id="cmp-metric-none"
                )
            )
            self._update_metric_status(
                "No dynamic metrics on any selected experiment."
            )
            return
        for key in self._metric_keys:
            view.append(
                ListItem(
                    Static(key), id=_metric_list_item_id(key)
                )
            )
        view.index = 0

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None or event.list_view.id != "cmp-metric-list":
            return
        try:
            index = event.list_view.index or 0
        except Exception:
            return
        if not (0 <= index < len(self._metric_keys)):
            return
        new_key = self._metric_keys[index]
        if new_key == self._selected_metric:
            return
        self._selected_metric = new_key
        self._refresh_metric_chart()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Pressing Enter on the chooser also refreshes the chart; the
        # actual change is handled by the highlight handler.
        self.on_list_view_highlighted(
            ListView.Highlighted(event.list_view, event.item)
        )

    def _refresh_metric_chart(self) -> None:
        if self._selected_metric is None:
            return
        width = self._chart_max_points()
        self._metric_histories = {}
        # Sequencing matters: each fetch routes through the same SQLite
        # meta DB connection. Funnel through one worker so the cursor
        # use is strictly serial.
        self._fetch_all_histories(self._selected_metric, max_points=width)

    def _chart_max_points(self) -> int:
        try:
            chart = self.query_one("#cmp-metric-chart", PlotextPlot)
        except Exception:
            return 200
        width = chart.size.width or chart.virtual_size.width
        if width <= 0:
            width = 80
        self._last_chart_width = width
        return max(80, width * 2)

    @work(thread=True, exclusive=True, group="cmp-data")
    def _fetch_all_histories(self, key: str, *, max_points: int) -> None:
        facade = self.facade
        if facade is None:
            return
        for exp in self._experiments:
            result = facade.get_metric_history(
                exp.id, key, max_points=max_points
            )
            self.app.call_from_thread(
                self._on_history_result, exp.id, key, result
            )

    @work(thread=True, exclusive=True, group="cmp-data")
    def _load_all_data(self) -> None:
        """Initial data load: metric histories first, then eval scores.

        Both fetches share the meta-DB connection inside the SQLite
        backend; running them through the same worker (in the same
        group with `exclusive=True`) is what keeps cursor usage strictly
        serial. `_refresh_metric_chart` reuses `_fetch_all_histories`
        directly for in-screen metric-switch refreshes — it also lives
        in this group, so it will cancel-and-replace any in-flight
        loader without inviting cursor contention.
        """

        facade = self.facade
        if facade is None:
            return
        key = self._selected_metric
        if key is not None:
            width = self._chart_max_points()
            for exp in self._experiments:
                result = facade.get_metric_history(
                    exp.id, key, max_points=width
                )
                self.app.call_from_thread(
                    self._on_history_result, exp.id, key, result
                )
        # Eval scores follow the histories so the metric chart fills
        # in first (most likely to be visible above the fold).
        for exp in self._experiments:
            ds_result = facade.get_eval_dataset_ids(exp.id)
            if not ds_result.ok:
                self.app.call_from_thread(
                    self._on_dataset_ids_failure, exp.id
                )
                continue
            dataset_ids = list(ds_result.unwrap() or [])
            self.app.call_from_thread(
                self._on_dataset_ids_result, exp.id, dataset_ids
            )
            for ds_id in dataset_ids:
                avg_result = facade.get_eval_average_scores(
                    exp.id, dataset_id=ds_id
                )
                if not avg_result.ok:
                    continue
                averages = dict(avg_result.unwrap() or {})
                self.app.call_from_thread(
                    self._on_average_scores_result,
                    exp.id,
                    ds_id,
                    averages,
                )

    def _on_history_result(
        self, experiment_id: str, key: str, result: Result[Any]
    ) -> None:
        if key != self._selected_metric:
            return
        if not result.ok:
            self._metric_histories[experiment_id] = None
        else:
            self._metric_histories[experiment_id] = result.unwrap()
        self._draw_metric_chart()

    def _draw_metric_chart(self) -> None:
        try:
            chart = self.query_one("#cmp-metric-chart", PlotextPlot)
        except Exception:
            return
        plt = chart.plt
        plt.clear_figure()
        plt.clear_data()
        plt.clear_color()
        any_series = False
        subsampled = False
        for i, exp in enumerate(self._experiments):
            history = self._metric_histories.get(exp.id)
            if history is None or not history.history:
                continue
            steps = [p.step for p in history.history]
            values = [p.value for p in history.history]
            plt.plot(
                steps,
                values,
                marker="braille",
                color=_plot_color_for(i),
                label=exp.name,
            )
            any_series = True
            if history.subsampled:
                subsampled = True
        if any_series:
            plt.title(self._selected_metric or "")
            plt.xlabel("step")
            plt.ylabel(self._selected_metric or "")
        chart.refresh()
        if not any_series:
            self._update_metric_status(
                "No data yet · waiting for series…"
            )
            return
        if subsampled:
            self._update_metric_status(
                f"{self._selected_metric} · subsampled to viewport width"
            )
        else:
            self._update_metric_status(
                f"{self._selected_metric}"
            )

    def _update_metric_status(self, message: str) -> None:
        try:
            self.query_one("#cmp-metric-status", Static).update(message)
        except Exception:
            pass

    # ----- eval scores comparison -----

    def _populate_evals_table_header(self) -> None:
        """Build the eval-scores table header before any data arrives.

        Each experiment gets its own column block; the score keys
        (rows) and dataset-id column become well-defined once
        per-experiment averages have been fetched, so this kicks the
        table off with the structure the user will see filled in.
        """

        table = self.query_one("#cmp-evals-table", DataTable)
        table.clear(columns=True)
        table.add_column("Dataset", key="cmp-eval-dataset")
        for i, exp in enumerate(self._experiments):
            label = Text(exp.name, style=f"bold {_rich_color_for(i)}")
            table.add_column(label, key=f"cmp-eval-exp-{exp.id}")

    def _on_dataset_ids_failure(self, experiment_id: str) -> None:
        self._dataset_ids[experiment_id] = []
        self._eval_scores[experiment_id] = {}
        self._rebuild_evals_table()

    def _on_dataset_ids_result(
        self, experiment_id: str, dataset_ids: list[str]
    ) -> None:
        self._dataset_ids[experiment_id] = dataset_ids
        self._eval_scores.setdefault(experiment_id, {})
        self._rebuild_evals_table()

    def _on_average_scores_result(
        self,
        experiment_id: str,
        dataset_id: str,
        averages: dict[str, float],
    ) -> None:
        per_exp = self._eval_scores.setdefault(experiment_id, {})
        per_exp[dataset_id] = averages
        self._rebuild_evals_table()

    def _rebuild_evals_table(self) -> None:
        """Redraw the eval-scores table from the accumulated dict.

        Called whenever a per-dataset fetch lands so partial data shows
        up as soon as it arrives. The table is fully cleared (rows
        only) on each rebuild to keep the renderer's invariants happy;
        columns were set up in `_populate_evals_table_header`.
        """

        try:
            table = self.query_one("#cmp-evals-table", DataTable)
        except Exception:
            return
        # Collect the dataset/score-key universe across all experiments.
        dataset_score_keys: dict[str, set[str]] = {}
        for per_exp in self._eval_scores.values():
            for ds_id, scores in per_exp.items():
                dataset_score_keys.setdefault(ds_id, set()).update(
                    scores.keys()
                )
        # Wipe rows but preserve columns.
        for existing_key in list(table.rows.keys()):
            try:
                table.remove_row(existing_key)
            except Exception:
                pass
        if not dataset_score_keys:
            table.add_row(
                Text("(no eval scores available)", style="dim"),
                *[Text("", style="dim") for _ in self._experiments],
                key="cmp-evals-empty",
            )
            return
        for ds_id in sorted(dataset_score_keys.keys()):
            for score_key in sorted(dataset_score_keys[ds_id]):
                row_key = f"cmp-eval-{ds_id}-{score_key}"
                cells: list[Text] = []
                cells.append(
                    Text(f"{ds_id} · {score_key}", style="dim")
                )
                values: list[float | None] = []
                for exp in self._experiments:
                    scores = self._eval_scores.get(exp.id, {}).get(
                        ds_id, {}
                    )
                    values.append(scores.get(score_key))
                differs = (
                    len({_score_repr(v) for v in values}) > 1
                )
                for value in values:
                    text = _format_score_cell(value)
                    if differs and value is not None:
                        text.stylize("$diff-changed")
                    cells.append(text)
                table.add_row(*cells, key=row_key)


def _score_repr(value: float | None) -> str:
    """Stable string repr for diff-detection of score values."""

    if value is None:
        return "<missing>"
    return f"{value:.6f}"


def _format_score_cell(value: float | None) -> Text:
    if value is None:
        return Text("—", style="dim")
    return Text(f"{value:.3f}")


__all__ = (
    "ComparisonScreen",
    "_ParamDiffRow",
    "_diff_static_params",
    "_shared_metric_keys",
)
