"""Experiment detail screen with the five tabs (Overview / Metrics / etc).

This screen is the heart of "what is happening in this experiment". It
implements the SPEC's tab contract:

- Five tabs (Overview, Metrics, Traces, Evals, Attachments) reachable
  by mnemonic accelerator (`O`/`M`/`T`/`E`/`A` — rendered as a
  highlighted letter in the tab label per the "no hidden shortcuts"
  invariant), by position (`1`–`5`), and by cycling (`[`/`]`).
- The accelerators are uppercase so they never shadow lowercase row
  verbs (`e` edit, `a` annotate) or the global `t` (theme).

All five tabs are now wired in: Overview, Metrics, Traces, Evals, and
Attachments — each backed by its own panel widget that lazy-loads the
first time the user activates the tab so a freshly opened detail
screen only pays for the data it shows.

The Overview tab shows experiment metadata, static and dynamic params,
tags, and the linked models with `e` to edit and `d` to delete
(constraint failures from the handler surface as non-fatal toasts).

The Metrics tab shows a metric chooser and renders the selected metric
as an in-terminal line chart via `textual-plotext`. The chart is
subsampled to the chart's rendered width by passing `max_points`
proportional to the available columns; on resize the chart is
re-fetched with the new viewport width so memory stays bounded even on
runs with millions of points.

All data fetching runs on Textual worker threads via the
`DataFacade`; the event loop never blocks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import events, work
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, Static, Tree

from lumlflow.schemas.experiments import (
    ExperimentDetails,
    ExperimentMetricHistory,
    ExperimentStatus,
)
from lumlflow.schemas.models import Model, UpdateModel
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment, PanelFrame
from lumlflow.tui.widgets.attachments_panel import AttachmentsPanel
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
)
from lumlflow.tui.widgets.evals_panel import EvalsPanel
from lumlflow.tui.widgets.metric_grid import (
    MetricCell,
    MetricGrid,
    MetricZoomView,
)
from lumlflow.tui.widgets.traces_panel import TracesPanel

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp


# Ordered list of (tab_id, label, mnemonic_index). Mnemonic index points
# to the character in the label that should be rendered highlighted to
# tell the user which key activates the tab. Position keys (1–5) and the
# cycle keys ([/]) round out the tab navigation contract.
TAB_DEFS: tuple[tuple[str, str, int], ...] = (
    ("overview", "Overview", 0),
    ("metrics", "Metrics", 0),
    ("traces", "Traces", 0),
    ("evals", "Evals", 0),
    ("attachments", "Attachments", 0),
)


# Plain-color counterparts used when rendering through `Static.update`
# (CSS variables are not expanded outside DataTable / Textual's own CSS
# rendering, so we use literal style names here).
_STATUS_PLAIN_STYLE: dict[ExperimentStatus, str] = {
    ExperimentStatus.ACTIVE: "bold cyan",
    ExperimentStatus.COMPLETED: "bold green",
    ExperimentStatus.ERROR: "bold red",
}

# Tag colour palette for rich Text rendering — eight stable colours
# matched against `hash(tag) % 8` so the same tag is consistently the
# same colour across panels (mirrors how DataTable cells colour tags
# via `$tag-N` variables; here we use plain colours because the meta
# header renders via `Static.update`).
_TAG_COLORS: tuple[str, ...] = (
    "cyan", "green", "red", "yellow",
    "magenta", "blue", "bright_cyan", "bright_magenta",
)


def _format_scalar(value: Any) -> str:
    """Render a param/metric value compactly.

    Floats are the common case for dynamic-metric snapshots; raw repr
    (``0.22761858501038598``) is unreadable in a dense card, so we cap
    them at six significant figures while leaving ints/strings intact.
    """

    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _format_duration(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 1:
        return f"{value * 1000:.0f} ms"
    if value < 60:
        return f"{value:.1f} s"
    minutes, seconds = divmod(int(value), 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _render_tab_label(
    label: str,
    mnemonic_index: int,
    position: int,
    active: bool,
) -> Text:
    """Render a tab segment label with the mnemonic letter highlighted.

    Each segment displays its position number (1–5) followed by the tab
    label with the mnemonic letter visibly highlighted. The mnemonic is
    the upper-case key that activates the tab (e.g. ``T`` for Traces);
    the rest of the label keeps its natural casing for readability. Rich
    style names are used directly here rather than CSS variables because
    the segments render via ``Static.update(Text)`` — CSS variables like
    ``$accent`` don't expand inside Rich Text. The CSS rule on the
    enclosing ``TabSegment`` paints the active background; this routine
    only owns the inline text colors for the active/idle states.
    """

    text = Text()
    # Inactive labels stay at full foreground weight (never `dim`) so the
    # idle tabs read clearly against the bar; the active pill is signalled
    # by its accent background rather than by dimming its neighbours. The
    # position number is kept but rendered subordinate so the label reads
    # first — the accelerator stays discoverable without dominating.
    base_style = "bold" if active else ""
    number_style = "bold" if active else "dim"
    text.append(f"{position} ", style=number_style)
    for i, ch in enumerate(label):
        if i == mnemonic_index:
            text.append(ch.upper(), style="bold underline")
        else:
            text.append(ch, style=base_style)
    return text


class TabSegment(Static):
    """One clickable segment of the tab bar.

    The segment renders the position number and the label with its
    mnemonic letter highlighted; clicking it activates the tab via the
    enclosing ``TabBar`` (which forwards to the screen's
    ``action_jump_tab``). The ``-active`` class swaps the background so
    the chosen tab reads as a depressed/selected segment.
    """

    DEFAULT_CSS = """
    TabSegment {
        width: auto;
        height: 1;
        padding: 0 2;
        margin-right: 1;
        background: $panel;
        color: $foreground;
    }
    TabSegment.-active {
        background: $accent;
        color: $background;
        text-style: bold;
    }
    TabSegment:hover {
        background: $panel-lighten-1;
        color: $text;
    }
    TabSegment.-active:hover {
        background: $accent;
        color: $background;
    }
    """

    def __init__(
        self,
        tab_id: str,
        label: str,
        mnemonic_index: int,
        position: int,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.tab_id = tab_id
        self._label = label
        self._mnemonic_index = mnemonic_index
        self._position = position
        self._active = False

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        if active:
            self.add_class("-active")
        else:
            self.remove_class("-active")
        self._refresh()

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        self.update(
            _render_tab_label(
                self._label,
                self._mnemonic_index,
                self._position,
                self._active,
            )
        )

    def on_click(self) -> None:
        self.post_message(TabBar.SegmentClicked(self.tab_id))


class TabBar(Horizontal):
    """A row of clickable / key-driven tab segments with mnemonic highlights."""

    DEFAULT_CSS = """
    TabBar {
        height: 1;
        background: $background;
        padding: 0 1;
    }
    """

    class SegmentClicked(Message):
        """Emitted when a tab segment is clicked.

        Bubbles to the host screen which routes through
        ``action_jump_tab`` — that path is what keymap and click stay in
        sync, so click and key produce identical state transitions.
        """

        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    def __init__(
        self,
        tabs: tuple[tuple[str, str, int], ...],
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._tabs = tabs
        self._active_id = tabs[0][0] if tabs else ""

    def compose(self) -> Iterable:  # type: ignore[override]
        for i, (tab_id, label, mnemonic_index) in enumerate(self._tabs):
            yield TabSegment(
                tab_id,
                label,
                mnemonic_index,
                i + 1,
                id=f"tab-seg-{tab_id}",
            )

    def on_mount(self) -> None:
        self._apply_active()

    def set_active(self, tab_id: str) -> None:
        if tab_id == self._active_id:
            return
        self._active_id = tab_id
        self._apply_active()

    def _apply_active(self) -> None:
        for seg in self.query(TabSegment):
            seg.set_active(seg.tab_id == self._active_id)


@dataclass
class _ModelRow:
    key: str
    name: str
    description: str
    tags: list[str]
    raw: Model


class ExperimentDetailScreen(BaseScreen):
    """Tabbed detail view for a single experiment.

    The screen owns the active tab and the per-tab state (selected
    metric, model selection, etc.). The detail data is fetched once on
    mount; mutations re-fetch only what changed.
    """

    DEFAULT_CSS = """
    ExperimentDetailScreen {
        layout: vertical;
    }
    ExperimentDetailScreen #exp-detail-body {
        height: 1fr;
        layout: vertical;
    }
    ExperimentDetailScreen #exp-detail-tabbar {
        height: 1;
        margin: 0 0 1 0;
    }
    ExperimentDetailScreen .tab-pane {
        height: 1fr;
        padding: 1 2;
    }
    ExperimentDetailScreen .tab-pane.-hidden {
        display: none;
    }
    ExperimentDetailScreen #pane-overview {
        layout: vertical;
        padding: 0 1;
    }
    ExperimentDetailScreen #overview-scroll {
        height: 1fr;
        width: 1fr;
    }
    ExperimentDetailScreen .overview-row {
        layout: horizontal;
        height: auto;
        width: 1fr;
    }
    ExperimentDetailScreen .overview-card {
        height: auto;
        margin: 0 1 1 0;
    }
    ExperimentDetailScreen .overview-card.-col {
        width: 1fr;
    }
    ExperimentDetailScreen .overview-card.-full {
        width: 1fr;
    }
    ExperimentDetailScreen .overview-card-last {
        margin-right: 0;
    }
    ExperimentDetailScreen #overview-meta {
        height: auto;
    }
    ExperimentDetailScreen #overview-params,
    ExperimentDetailScreen #overview-dynamic,
    ExperimentDetailScreen #overview-tags {
        height: auto;
    }
    ExperimentDetailScreen #overview-models-table {
        height: auto;
        max-height: 12;
    }
    ExperimentDetailScreen #pane-metrics {
        layout: vertical;
    }
    ExperimentDetailScreen #metrics-grid {
        height: 1fr;
        display: block;
    }
    ExperimentDetailScreen #metrics-grid.-hidden {
        display: none;
    }
    ExperimentDetailScreen #metrics-zoom {
        height: 1fr;
        display: block;
    }
    ExperimentDetailScreen #metrics-zoom.-hidden {
        display: none;
    }
    ExperimentDetailScreen .empty-pane {
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }
    """

    BINDINGS = [
        # Tab mnemonics. Lowercase letters are the primary accelerators so
        # they line up with the visible tab labels (press `t` for Traces);
        # the uppercase variants stay bound as aliases for muscle memory.
        # `e` no longer edits a model (that moved to Enter on the models
        # row) so it is free to mean Evals, and `t` switches to Traces on
        # this screen (theme lives on Ctrl+T so it never collides).
        Binding("o", "jump_tab('overview')", "Overview", show=False),
        Binding("m", "jump_tab('metrics')", "Metrics", show=False),
        Binding("t", "jump_tab('traces')", "Traces", show=False),
        Binding("e", "jump_tab('evals')", "Evals", show=False),
        Binding("a", "jump_tab('attachments')", "Attachments", show=False),
        Binding("O", "jump_tab('overview')", "Overview", show=False),
        Binding("M", "jump_tab('metrics')", "Metrics", show=False),
        Binding("T", "jump_tab('traces')", "Traces", show=False),
        Binding("E", "jump_tab('evals')", "Evals", show=False),
        Binding("A", "jump_tab('attachments')", "Attachments", show=False),
        # Position keys.
        Binding("1", "jump_tab_index(0)", "Tab 1", show=False),
        Binding("2", "jump_tab_index(1)", "Tab 2", show=False),
        Binding("3", "jump_tab_index(2)", "Tab 3", show=False),
        Binding("4", "jump_tab_index(3)", "Tab 4", show=False),
        Binding("5", "jump_tab_index(4)", "Tab 5", show=False),
        # Cycle keys. `Tab`/`Shift+Tab` move between tabs on every tab —
        # the Metrics mini-chart grid is navigated with the arrow keys,
        # so Tab no longer needs a per-tab special case.
        Binding("[", "prev_tab", "Prev tab", show=False),
        Binding("]", "next_tab", "Next tab", show=False),
        Binding("tab", "next_tab", "Next tab", show=False),
        Binding("shift+tab", "prev_tab", "Prev tab", show=False),
        # Row verbs scoped to the models list on the Overview tab. Editing
        # a model is reached with Enter on its row (see
        # ``on_data_table_row_selected``); delete / yank act on the row
        # under the cursor without needing focus.
        Binding("d", "delete_focused_model", "Delete model", show=False),
        Binding("y", "yank_focused_model", "Yank id", show=False),
        # Publish: on the Overview tab with a focused model row, `p`
        # publishes that model; anywhere else it publishes the whole
        # experiment (the screen always knows which one it shows).
        Binding("p", "publish_focused", "Publish", show=False),
    ]

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        experiment_id: str,
        experiment_name: str | None = None,
        group_name: str | None = None,
        initial_tab: str = "overview",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._experiment_id = experiment_id
        self._experiment_name = experiment_name
        self._group_name = group_name
        self._active_tab: str = initial_tab
        # Detail loaded asynchronously after mount.
        self._details: ExperimentDetails | None = None
        # Models list (mirrors the experiment details models field, kept
        # as its own state so edit/delete can update in place).
        self._model_rows: list[_ModelRow] = []
        # Metric tab state.
        # ``_metric_keys`` is the ordered keyset rendered as mini-charts;
        # ``_metric_history`` caches the most recently fetched series
        # for the zoomed metric so toggle flips can redraw without a
        # refetch round-trip. ``_zoomed_metric`` is non-None while the
        # zoom view owns the pane.
        self._metric_keys: list[str] = []
        self._metric_history: dict[str, ExperimentMetricHistory] = {}
        self._zoomed_metric: str | None = None

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="exp-detail-body"):
            yield TabBar(TAB_DEFS, id="exp-detail-tabbar")
            with Container(id="pane-overview", classes="tab-pane"):
                with VerticalScroll(id="overview-scroll"):
                    # About card — full width on top so the experiment
                    # name, status, group, and description anchor the view.
                    with PanelFrame(
                        title="About",
                        classes="overview-card -full overview-card-last",
                        id="overview-about-card",
                    ):
                        yield Static(
                            "Loading experiment…", id="overview-meta"
                        )
                    # Static params + dynamic metric snapshot live
                    # side-by-side on wider terminals; on a narrow viewport
                    # the row falls back to a stacked layout.
                    with Horizontal(classes="overview-row"):
                        with PanelFrame(
                            title="Static parameters",
                            classes="overview-card -col",
                            id="overview-params-card",
                        ):
                            yield Static("(none)", id="overview-params")
                        with PanelFrame(
                            title="Dynamic metrics",
                            classes="overview-card -col overview-card-last",
                            id="overview-dynamic-card",
                        ):
                            yield Static("(none)", id="overview-dynamic")
                    # Tags as its own card so the chips have room to wrap.
                    with PanelFrame(
                        title="Tags",
                        classes="overview-card -full overview-card-last",
                        id="overview-tags-card",
                    ):
                        yield Static("(none)", id="overview-tags")
                    # Linked models gets a full-width card with the table.
                    with PanelFrame(
                        title="Linked models",
                        classes="overview-card -full overview-card-last",
                        id="overview-models-card",
                    ):
                        yield DataTable(
                            id="overview-models-table",
                            cursor_type="row",
                            zebra_stripes=True,
                        )
            with Container(id="pane-metrics", classes="tab-pane"):
                yield MetricGrid(id="metrics-grid")
                yield MetricZoomView(id="metrics-zoom")
            with Container(id="pane-traces", classes="tab-pane"):
                yield TracesPanel(
                    facade=self._facade,
                    experiment_id=self._experiment_id,
                    experiment_name=self._experiment_name,
                    group_name=self._group_name,
                    id="pane-traces-panel",
                )
            with Container(id="pane-evals", classes="tab-pane"):
                yield EvalsPanel(
                    facade=self._facade,
                    experiment_id=self._experiment_id,
                    experiment_name=self._experiment_name,
                    group_name=self._group_name,
                    id="pane-evals-panel",
                )
            with Container(id="pane-attachments", classes="tab-pane"):
                yield AttachmentsPanel(
                    facade=self._facade,
                    experiment_id=self._experiment_id,
                    experiment_name=self._experiment_name,
                    group_name=self._group_name,
                    id="pane-attachments-panel",
                )

    def on_mount(self) -> None:
        # Set up the models table columns now so the table is well-formed
        # before any data arrives.
        models_table = self.query_one("#overview-models-table", DataTable)
        models_table.add_columns("Name", "Tags", "Description", "Size")
        # Show only the initial pane.
        self._refresh_pane_visibility()
        # Metrics tab: start on the grid; the zoom view is hidden until
        # the user opens it.
        self._show_metric_grid()
        # Focus the initial pane's primary surface so its cursor is live
        # without a preliminary Tab press (models table on Overview,
        # first mini-chart on Metrics, and so on).
        self._notify_pane_activated(self._active_tab)
        # Trigger the initial data fetch.
        if self.facade is not None:
            self._fetch_details()

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        segments = [BreadcrumbSegment("Groups")]
        if self._group_name:
            segments.append(BreadcrumbSegment(self._group_name))
        name = self._experiment_name or (
            self._details.name if self._details is not None else self._experiment_id
        )
        segments.append(BreadcrumbSegment(name))
        return tuple(segments)

    def footer_scopes(self) -> tuple[Scope, ...]:
        """Footer hints follow the active tab.

        Each tab has a distinct primary surface (models table, chart
        grid, browse tables, file tree), so the footer only shows the
        keys that actually work there. The tab bar itself documents the
        tab-jump keys.
        """

        per_tab: dict[str, tuple[Scope, ...]] = {
            "overview": ("global", "tabs", "models", "experiment"),
            "metrics": ("global", "tabs", "metrics", "experiment"),
            "traces": ("global", "tabs", "list", "experiment"),
            "evals": ("global", "tabs", "list", "evals", "experiment"),
            "attachments": ("global", "tabs", "attachments", "experiment"),
        }
        return per_tab.get(self._active_tab, ("global", "tabs", "experiment"))

    # ----- facade access -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        return getattr(self.app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- detail fetch -----

    @work(thread=True, exclusive=True, group="experiment-detail")
    def _fetch_details(self) -> None:
        facade = self.facade
        if facade is None:
            self.app.call_from_thread(
                self._on_details_failure, "facade unavailable"
            )
            return
        result = facade.get_experiment(self._experiment_id)
        self.app.call_from_thread(self._on_details_result, result)

    def _on_details_result(self, result: Result[Any]) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "unknown error"
            self._on_details_failure(msg)
            return
        details: ExperimentDetails = result.unwrap()
        self._details = details
        self._populate_overview(details)
        self._populate_metric_keys(details)
        # Refresh the breadcrumb now that the experiment name is known.
        self._lumlflow_app._sync_chrome_to_screen()

    def _on_details_failure(self, message: str) -> None:
        self._lumlflow_app.show_toast(
            f"Could not load experiment: {message}", severity="error"
        )
        # Surface the error inline so the screen is still informative.
        try:
            self.query_one("#overview-meta", Static).update(
                f"Could not load experiment: {message}"
            )
        except Exception:
            pass

    # ----- overview tab -----

    def _populate_overview(self, details: ExperimentDetails) -> None:
        # Meta header — name, status, duration, group, created.
        try:
            meta = self.query_one("#overview-meta", Static)
        except Exception:
            return
        status_style = _STATUS_PLAIN_STYLE.get(details.status, "bold")
        meta_text = Text()
        meta_text.append(details.name, style="bold")
        meta_text.append("\n")
        meta_text.append("status: ")
        meta_text.append(details.status.value, style=status_style)
        meta_text.append("    duration: ")
        meta_text.append(_format_duration(details.duration), style="dim")
        if details.group_name:
            meta_text.append("    group: ")
            meta_text.append(details.group_name, style="dim")
        if details.created_at is not None:
            meta_text.append("    created: ")
            meta_text.append(
                details.created_at.strftime("%Y-%m-%d %H:%M"), style="dim"
            )
        if details.description:
            meta_text.append("\n\n")
            meta_text.append(details.description)
        meta.update(meta_text)

        # Static params.
        params = self.query_one("#overview-params", Static)
        params.update(self._format_kv(details.static_params))

        # Dynamic params — these are the per-metric latest values stored
        # on the experiment row. They double as a quick metric snapshot
        # and as the list of metric keys for the Metrics tab.
        dynamic = self.query_one("#overview-dynamic", Static)
        dynamic.update(self._format_kv(details.dynamic_params))

        # Tags.
        tags = self.query_one("#overview-tags", Static)
        if details.tags:
            text = Text()
            for i, tag in enumerate(details.tags):
                if i > 0:
                    text.append(" ")
                color = _TAG_COLORS[hash(tag) % len(_TAG_COLORS)]
                text.append(tag, style=f"bold {color}")
            tags.update(text)
        else:
            tags.update("(none)")

        # Models.
        self._set_model_rows(details.models or [])

    @staticmethod
    def _format_kv(value: dict[str, Any] | None) -> Text:
        if not value:
            return Text("(none)", style="dim")
        text = Text()
        for i, (k, v) in enumerate(value.items()):
            if i > 0:
                text.append("\n")
            text.append(f"{k}", style="bold")
            text.append(" = ")
            text.append(_format_scalar(v))
        return text

    def _set_model_rows(self, models: list[Model]) -> None:
        self._model_rows = [
            _ModelRow(
                key=m.id,
                name=m.name,
                description=m.description or "",
                tags=m.tags or [],
                raw=m,
            )
            for m in models
        ]
        self._refresh_models_table()

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KiB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MiB"
        return f"{size / (1024 * 1024 * 1024):.2f} GiB"

    # ----- metrics tab -----

    def _populate_metric_keys(self, details: ExperimentDetails) -> None:
        # The `dynamic_params` dict on the experiment row keys each metric
        # logged by the SDK (with the last logged value); use its keys as
        # the metric set rendered as mini-charts in the grid.
        keys = sorted((details.dynamic_params or {}).keys())
        self._metric_keys = keys
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
        except Exception:
            return
        grid.set_metric_keys(keys)
        # If the zoomed metric is no longer in the keyset, drop the zoom
        # view so we don't show stale state.
        if self._zoomed_metric is not None and self._zoomed_metric not in keys:
            self._zoomed_metric = None
            self._show_metric_grid()
        # If the user is already on the Metrics tab (e.g. the screen
        # opened straight onto it) and no cell holds focus yet, land on
        # the first chart so the arrow keys work immediately.
        if (
            self._active_tab == "metrics"
            and self._zoomed_metric is None
            and keys
            and not isinstance(self.focused, MetricCell)
        ):
            grid.focus_first_cell()

    @work(thread=True, group="experiment-metric")
    def _fetch_metric_history(self, key: str, *, max_points: int) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.get_metric_history(
            self._experiment_id, key, max_points=max_points
        )
        self.app.call_from_thread(self._on_metric_result, result, key)

    def _on_metric_result(self, result: Result[Any], key: str) -> None:
        if not result.ok:
            err = result.error
            self._lumlflow_app.show_toast(
                f"Metric load failed: {err.message if err else 'error'}",
                severity="error",
            )
            return
        history: ExperimentMetricHistory = result.unwrap()
        # Cache by key so toggle flips on the zoom view can redraw
        # without re-fetching; the grid cell also keeps its own copy.
        self._metric_history[key] = history
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
        except Exception:
            grid = None
        if grid is not None:
            grid.apply_history(history)
        # If the zoom view is active on this metric, push the latest
        # history through so the chart redraws with the current toggles.
        if self._zoomed_metric == key:
            try:
                zoom = self.query_one("#metrics-zoom", MetricZoomView)
                zoom.set_history(history)
            except Exception:
                pass

    # ----- grid messages -----

    def on_metric_grid_history_needed(
        self, event: MetricGrid.HistoryNeeded
    ) -> None:
        """Honour a grid cell's request for its metric history."""

        event.stop()
        self._fetch_metric_history(event.metric_key, max_points=event.max_points)

    def on_metric_grid_zoom_requested(
        self, event: MetricGrid.ZoomRequested
    ) -> None:
        """Open the zoom view on the metric the user pressed Enter on."""

        event.stop()
        self._open_zoom(event.metric_key)

    # ----- zoom view -----

    def _open_zoom(self, metric_key: str) -> None:
        try:
            zoom = self.query_one("#metrics-zoom", MetricZoomView)
        except Exception:
            return
        self._zoomed_metric = metric_key
        zoom.set_metric_key(metric_key)
        cached = self._metric_history.get(metric_key)
        if cached is not None:
            zoom.set_history(cached)
        else:
            # Cell width is a reasonable proxy for grid charts; for the
            # zoom view we ask for a richer subsample so the larger
            # canvas has more detail.
            self._fetch_metric_history(metric_key, max_points=400)
        self._show_metric_zoom()
        # Focus the zoom panel so ←/→ metric stepping and Esc target
        # it directly without a Tab press.
        try:
            zoom.focus()
        except Exception:
            pass

    def _close_zoom(self) -> None:
        zoomed = self._zoomed_metric
        self._zoomed_metric = None
        self._show_metric_grid()
        # Hand focus back to the cell that was zoomed so arrow keys
        # continue from where the user left off.
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
        except Exception:
            return
        if zoomed is None or not grid.focus_cell(zoomed):
            grid.focus_first_cell()

    def on_metric_zoom_view_step_requested(
        self, event: MetricZoomView.StepRequested
    ) -> None:
        """`←`/`→` in the zoom view step to the adjacent metric."""

        event.stop()
        if self._zoomed_metric is None or not self._metric_keys:
            return
        try:
            index = self._metric_keys.index(self._zoomed_metric)
        except ValueError:
            return
        target = index + event.delta
        if not (0 <= target < len(self._metric_keys)):
            return
        self._open_zoom(self._metric_keys[target])

    def _focus_metrics_surface(self) -> None:
        """Focus whatever the Metrics tab is currently showing.

        The zoom view when it is open, otherwise the first mini-chart
        (or the grid body while the cells are still loading) — so the
        arrow keys work the moment the tab activates.
        """

        if self._zoomed_metric is not None:
            try:
                self.query_one("#metrics-zoom", MetricZoomView).focus()
            except Exception:
                pass
            return
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
        except Exception:
            return
        grid.focus_first_cell()

    def action_grid_nav(self) -> None:
        """Palette entry for `metrics.grid_nav`: land on the chart grid."""

        if self._active_tab != "metrics":
            self.action_jump_tab("metrics")
        else:
            self._focus_metrics_surface()

    def _show_metric_grid(self) -> None:
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
            zoom = self.query_one("#metrics-zoom", MetricZoomView)
        except Exception:
            return
        grid.remove_class("-hidden")
        grid.display = True
        zoom.add_class("-hidden")
        zoom.display = False

    def _show_metric_zoom(self) -> None:
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
            zoom = self.query_one("#metrics-zoom", MetricZoomView)
        except Exception:
            return
        grid.add_class("-hidden")
        grid.display = False
        zoom.remove_class("-hidden")
        zoom.display = True

    def _is_zoom_active(self) -> bool:
        return (
            self._active_tab == "metrics"
            and self._zoomed_metric is not None
        )

    def on_key(self, event: events.Key) -> None:
        # Esc returns from the zoom view to the grid without popping
        # the screen — the zoom view is an in-screen overlay, so Esc
        # closes it first; a second Esc pops the screen as usual.
        # (`←`/`→` step between metrics inside the zoom view instead.)
        if event.key != "escape":
            return
        if not self._is_zoom_active():
            return
        self._close_zoom()
        event.stop()

    # ----- tab switching -----

    def _refresh_pane_visibility(self) -> None:
        # Hide all panes, then show the active one.
        for tab_id, _, _ in TAB_DEFS:
            pane = self._pane(tab_id)
            if pane is None:
                continue
            if tab_id == self._active_tab:
                pane.remove_class("-hidden")
                pane.display = True
            else:
                pane.add_class("-hidden")
                pane.display = False
        try:
            tabbar = self.query_one("#exp-detail-tabbar", TabBar)
            tabbar.set_active(self._active_tab)
        except Exception:
            pass

    def _pane(self, tab_id: str) -> Container | None:
        try:
            return self.query_one(f"#pane-{tab_id}", Container)
        except Exception:
            return None

    def on_tab_bar_segment_clicked(
        self, event: TabBar.SegmentClicked
    ) -> None:
        """Route a clicked tab segment through the same path as the
        keyboard mnemonic so click and key produce the same transition."""

        event.stop()
        self.action_jump_tab(event.tab_id)

    def action_jump_tab(self, tab_id: str) -> None:
        if tab_id == self._active_tab:
            return
        # Guard: tab_id must be a known tab.
        known = {t[0] for t in TAB_DEFS}
        if tab_id not in known:
            return
        self._active_tab = tab_id
        self._refresh_pane_visibility()
        self._notify_pane_activated(tab_id)
        # Footer scopes depend on the active tab — re-point the chrome.
        self._lumlflow_app._sync_chrome_to_screen()

    def _notify_pane_activated(self, tab_id: str) -> None:
        """Trigger lazy loads on the newly visible pane and focus its table.

        Traces / Evals / Attachments only fetch when their tab is
        actually opened — paying the read cost up-front would slow the
        initial detail screen render for users who only want to scan
        metrics. Each pane's primary interactive widget (the traces /
        evals / attachments table) is focused as well so ``j``/``k`` /
        ``Enter`` work immediately, without a preliminary ``Tab`` press.
        """

        if tab_id == "overview":
            try:
                self.query_one("#overview-models-table", DataTable).focus()
            except Exception:
                pass
        elif tab_id == "metrics":
            self._focus_metrics_surface()
        elif tab_id == "traces":
            try:
                panel = self.query_one("#pane-traces-panel", TracesPanel)
            except Exception:
                return
            panel.start()
            try:
                panel.query_one("#traces-table", DataTable).focus()
            except Exception:
                pass
        elif tab_id == "evals":
            try:
                evals = self.query_one("#pane-evals-panel", EvalsPanel)
            except Exception:
                return
            evals.start()
            try:
                evals.query_one("#evals-table", DataTable).focus()
            except Exception:
                pass
        elif tab_id == "attachments":
            try:
                attachments = self.query_one(
                    "#pane-attachments-panel", AttachmentsPanel
                )
            except Exception:
                return
            attachments.start()
            # Attachments uses a Tree (not a DataTable) for the file
            # listing; focus it so j/k/Enter work right away.
            try:
                attachments.query_one("#attachments-tree", Tree).focus()
            except Exception:
                pass

    def action_jump_tab_index(self, index: int) -> None:
        if not (0 <= index < len(TAB_DEFS)):
            return
        self.action_jump_tab(TAB_DEFS[index][0])

    def action_prev_tab(self) -> None:
        ids = [t[0] for t in TAB_DEFS]
        try:
            i = ids.index(self._active_tab)
        except ValueError:
            return
        self.action_jump_tab(ids[(i - 1) % len(ids)])

    def action_next_tab(self) -> None:
        ids = [t[0] for t in TAB_DEFS]
        try:
            i = ids.index(self._active_tab)
        except ValueError:
            return
        self.action_jump_tab(ids[(i + 1) % len(ids)])

    # ----- model edit / delete (scoped to overview tab) -----

    def _focused_model_row(self) -> _ModelRow | None:
        if self._active_tab != "overview":
            return None
        try:
            table = self.query_one("#overview-models-table", DataTable)
        except Exception:
            return None
        if table.row_count == 0 or not self._model_rows:
            return None
        try:
            row_index = table.cursor_row
            if not (0 <= row_index < len(self._model_rows)):
                return None
            return self._model_rows[row_index]
        except Exception:
            return None

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        # Enter on a linked-model row opens its edit dialog. DataTable
        # consumes Enter for its own `select_cursor`, so we translate the
        # bubbled `RowSelected` into the edit action — the same pattern the
        # experiments list uses for drill-in.
        if event.data_table.id != "overview-models-table":
            return
        self.action_edit_focused_model()

    def action_edit_focused_model(self) -> None:
        row = self._focused_model_row()
        if row is None:
            return
        dialog = EditEntityDialog(
            title=f"Edit model · {row.name}",
            name=row.name,
            description=row.raw.description,
            tags=row.raw.tags,
        )
        model_id = row.key
        self.app.push_screen(
            dialog,
            callback=lambda res: self._on_model_edit_submitted(model_id, res),
        )

    def _on_model_edit_submitted(
        self, model_id: str, result: EntityEditResult | None
    ) -> None:
        if result is None:
            return
        body = UpdateModel(
            name=result.name,
            description=result.description,
            tags=result.tags,
        )
        if (
            body.name is None
            and body.description is None
            and body.tags is None
        ):
            return
        self._run_model_update(model_id, body)

    @work(thread=True, group="experiment-model-update")
    def _run_model_update(self, model_id: str, body: UpdateModel) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.update_model(model_id, body)
        self.app.call_from_thread(self._on_model_update_result, result, model_id)

    def _on_model_update_result(
        self, result: Result[Any], model_id: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "update failed"
            self._lumlflow_app.show_toast(
                f"Edit failed: {msg}", severity="error"
            )
            return
        updated_model: Model = result.unwrap()
        # Replace the row in-place rather than reloading the whole detail.
        for i, row in enumerate(self._model_rows):
            if row.key == model_id:
                self._model_rows[i] = _ModelRow(
                    key=updated_model.id,
                    name=updated_model.name,
                    description=updated_model.description or "",
                    tags=updated_model.tags or [],
                    raw=updated_model,
                )
                break
        self._refresh_models_table()
        self._lumlflow_app.show_toast(
            "Model updated.", severity="success", duration=2.0
        )

    def action_delete_focused_model(self) -> None:
        row = self._focused_model_row()
        if row is None:
            return
        dialog = ConfirmDialog(
            title="Delete model",
            message=(
                f"Delete model {row.name!r}? This will detach it from the "
                "experiment and cannot be undone."
            ),
            confirm_label="Delete",
            destructive=True,
        )
        model_id = row.key
        self.app.push_screen(
            dialog,
            callback=lambda confirmed: self._on_model_delete_confirmed(
                model_id, confirmed
            ),
        )

    def _on_model_delete_confirmed(
        self, model_id: str, confirmed: bool | None
    ) -> None:
        if not confirmed:
            return
        self._run_model_delete(model_id)

    @work(thread=True, group="experiment-model-delete")
    def _run_model_delete(self, model_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.delete_model(model_id)
        self.app.call_from_thread(self._on_model_delete_result, result, model_id)

    def _on_model_delete_result(
        self, result: Result[Any], model_id: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "delete failed"
            if err and err.is_conflict:
                self._lumlflow_app.show_toast(
                    f"Delete blocked: {msg}", severity="warning"
                )
            else:
                self._lumlflow_app.show_toast(
                    f"Delete blocked: {msg}", severity="error"
                )
            return
        self._model_rows = [r for r in self._model_rows if r.key != model_id]
        self._refresh_models_table()
        self._lumlflow_app.show_toast(
            "Model deleted.", severity="success", duration=2.0
        )

    def _refresh_models_table(self) -> None:
        try:
            table = self.query_one("#overview-models-table", DataTable)
        except Exception:
            return
        table.clear()
        if not self._model_rows:
            # No models: drop the row cursor so the placeholder doesn't
            # render as a full-width highlighted (selected-looking) bar.
            table.cursor_type = "none"
            table.add_row(
                Text("No linked models", style="dim"),
                Text(""),
                Text(""),
                Text(""),
                key="__no_models__",
            )
            return
        table.cursor_type = "row"
        for row in self._model_rows:
            tags_text = Text()
            for i, tag in enumerate(row.tags):
                if i > 0:
                    tags_text.append(" ")
                color_index = hash(tag) % 8
                tags_text.append(tag, style=f"bold $tag-{color_index}")
            size = row.raw.size
            size_text = (
                Text(self._format_size(size), style="dim")
                if size is not None
                else Text("—", style="dim")
            )
            table.add_row(
                Text(row.name),
                tags_text,
                Text(row.description, overflow="ellipsis"),
                size_text,
                key=row.key,
            )

    def action_yank_focused_model(self) -> None:
        row = self._focused_model_row()
        if row is None:
            return
        self._lumlflow_app.yank_to_clipboard(row.key, label="model id")

    # ----- publish -----

    def action_publish_focused(self) -> None:
        """`p`: publish the focused model row, or the experiment.

        On the Overview tab with the cursor on a linked model, publish
        exactly that model (single-model cloud upload). Everywhere
        else, publish the experiment as before.
        """

        row = self._focused_model_row()
        if row is None:
            self.action_publish_experiment()
            return
        from lumlflow.tui.screens.cloud_publish import CloudPublishScreen

        screen = CloudPublishScreen(
            facade=self.facade,
            experiment_id=self._experiment_id,
            experiment_name=self._experiment_name or self._experiment_id,
            model_id=row.key,
            model_name=row.name,
            breadcrumb_prefix=self.breadcrumb_segments(),
        )
        self.app.push_screen(screen)

    def action_publish_experiment(self) -> None:
        """Open the cloud publish flow against this experiment."""

        from lumlflow.tui.screens.cloud_publish import CloudPublishScreen

        name = (
            self._details.name
            if self._details is not None
            else (self._experiment_name or self._experiment_id)
        )
        screen = CloudPublishScreen(
            facade=self.facade,
            experiment_id=self._experiment_id,
            experiment_name=name,
            breadcrumb_prefix=self.breadcrumb_segments(),
        )
        self.app.push_screen(screen)

    # ----- live refresh -----

    def refresh_live(self) -> None:
        """Refresh whatever is currently visible in this detail screen.

        Strategy:
        - Always re-fetch experiment details (status flips, new dynamic
          metric snapshot values) so the overview/header stay current.
        - If the metrics tab is active, re-fetch the histories of the
          visible charts in place so new points appear without losing
          the user's grid cursor or open zoom view.
        - Delegate to the active panel (traces/evals/attachments) so it
          can refresh its own visible rows.
        """

        if self.facade is None:
            return
        self._refresh_details()
        if self._active_tab == "metrics":
            self._refresh_metrics_visible()
        # Forward refresh into the active panel so it can update its own
        # visible window.
        if self._active_tab == "traces":
            try:
                panel = self.query_one("#pane-traces-panel", TracesPanel)
            except Exception:
                return
            if hasattr(panel, "refresh_live"):
                panel.refresh_live()
        elif self._active_tab == "evals":
            try:
                evals = self.query_one("#pane-evals-panel", EvalsPanel)
            except Exception:
                return
            if hasattr(evals, "refresh_live"):
                evals.refresh_live()

    def _refresh_metrics_visible(self) -> None:
        """Re-fetch the histories of every visible metric chart in place."""

        # The zoom view, if open, owns a single richer fetch with a
        # generous max_points so the larger canvas keeps its detail.
        if self._zoomed_metric is not None:
            self._fetch_metric_history(self._zoomed_metric, max_points=400)
            return
        # Otherwise re-issue per-cell fetches sized to each cell's
        # current width so live updates land at the right detail.
        try:
            grid = self.query_one("#metrics-grid", MetricGrid)
        except Exception:
            return
        grid.request_refresh_visible()

    @work(thread=True, exclusive=True, group="experiment-detail-refresh")
    def _refresh_details(self) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.get_experiment(self._experiment_id)
        self.app.call_from_thread(self._on_refresh_details_result, result)

    def _on_refresh_details_result(self, result: Result[Any]) -> None:
        if not result.ok:
            return
        details: ExperimentDetails = result.unwrap()
        # Update only the affected widgets — re-running `_populate_overview`
        # rebuilds the meta header and dynamic params snapshot in place.
        prev = self._details
        self._details = details
        self._populate_overview(details)
        # If new metric keys appeared (e.g. the running script started
        # logging a new metric), reflect that in the metrics list.
        prev_keys = sorted((prev.dynamic_params or {}).keys()) if prev else []
        new_keys = sorted((details.dynamic_params or {}).keys())
        if new_keys != prev_keys:
            self._populate_metric_keys(details)


__all__ = (
    "ExperimentDetailScreen",
    "TabBar",
    "TabSegment",
    "TAB_DEFS",
)
