"""EvalsPanel widget — the body of the Evals tab.

Renders a paginated evals table for one experiment with dynamic
columns derived from the handler's `EvalColumns` (one column per
input / output / ref / score / metadata key). Score cells are colored
on a low→high gradient so a table of scores reads as a heatmap at a
glance per the SPEC's visual contract.

The widget exposes the same list contract every screen uses: `/` for
incremental search, `f` for the advanced DSL filter (live-validated
against `validate_evals_filter`), `s` for the sort chooser, `Enter`
to open the eval detail screen, `j`/`k` for movement, and lazy
pagination via cursor + prefetch. A dataset selector switches between
the experiment's eval datasets and surfaces average scores per
selected dataset.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Input, ListItem, ListView, Static

from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import Eval, EvalColumns
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.widgets.dialogs import (
    FilterEditorDialog,
    FilterValidation,
    SortChooserDialog,
    SortChooserResult,
)

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp

PAGE_SIZE = 50

# Sentinel value used in the dataset selector to represent the
# "all datasets" entry. The handler accepts `dataset_id=None`.
ALL_DATASETS = "__all__"

_SORT_FIELDS: list[tuple[str, str]] = [
    ("created_at", "Created"),
    ("updated_at", "Updated"),
    ("dataset_id", "Dataset"),
]


# Heatmap palette for numeric scores in [0, 1]. We use eight stops in
# Rich style names (avoiding CSS variables — the table renders cells
# via `Text(style=...)` which doesn't expand `$tokens`).
_HEATMAP_STOPS: tuple[str, ...] = (
    "red",
    "bright_red",
    "yellow",
    "bright_yellow",
    "green3",
    "green",
    "bright_green",
    "bright_cyan",
)


def _heatmap_style(score: float, low: float, high: float) -> str:
    """Pick a heatmap color for `score` relative to the [low, high] range.

    Scores outside the range are clamped. A flat range (low == high)
    renders all cells with the middle stop so there is no false
    gradient. Returns a Rich style string suitable for `Text(style=...)`.
    """

    if not _HEATMAP_STOPS:
        return ""
    if high <= low:
        color = _HEATMAP_STOPS[len(_HEATMAP_STOPS) // 2]
        return f"bold {color}"
    clamped = max(low, min(high, score))
    fraction = (clamped - low) / (high - low)
    index = min(
        len(_HEATMAP_STOPS) - 1,
        max(0, int(fraction * len(_HEATMAP_STOPS))),
    )
    color = _HEATMAP_STOPS[index]
    return f"bold {color}"


def _format_score(value: Any) -> str:
    """Render a numeric score with three significant digits.

    Non-numeric scores fall back to `str(value)` so the column stays
    informative for textual scores. `None` becomes a dim em-dash.
    """

    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        if value == int(value):
            return str(int(value))
        return f"{value:.3f}"
    return str(value)


def _format_cell(value: Any) -> str:
    """Compact rendering of an inputs/outputs/refs/metadata field.

    Dicts and lists serialise as a short JSON-ish summary so the table
    still fits a viewport. Long strings are clipped to a single line —
    full content is visible on the eval detail screen.
    """

    if value is None:
        return "—"
    if isinstance(value, str):
        if "\n" in value:
            return value.split("\n", 1)[0] + " …"
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return _format_score(value)
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}=…" for k in list(value.keys())[:3]) + "}"
    return str(value)


def _numeric_score(value: Any) -> float | None:
    """Return `value` as a float if it represents a numeric score."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


@dataclass
class _EvalRow:
    key: str
    eval: Eval


class EvalsPanel(Widget):
    """Lazy-paginated evals table with heatmap + dataset selector."""

    DEFAULT_CSS = """
    EvalsPanel {
        layout: vertical;
        height: 1fr;
    }
    EvalsPanel #evals-controls {
        height: auto;
        padding: 0 2;
    }
    EvalsPanel #evals-dataset-list {
        width: 28;
        height: auto;
        max-height: 6;
        border-right: solid $panel;
    }
    EvalsPanel #evals-controls-right {
        width: 1fr;
        layout: vertical;
        height: auto;
    }
    EvalsPanel #evals-search {
        margin: 0 2;
        display: none;
    }
    EvalsPanel #evals-search.-visible {
        display: block;
    }
    EvalsPanel #evals-sort-status {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    EvalsPanel #evals-filter-status {
        height: 1;
        padding: 0 2;
        color: $warning;
    }
    EvalsPanel #evals-filter-status.-empty {
        display: none;
    }
    EvalsPanel #evals-avg-scores {
        height: auto;
        padding: 0 2;
        color: $text-muted;
    }
    EvalsPanel #evals-avg-scores.-empty {
        display: none;
    }
    EvalsPanel #evals-table {
        height: 1fr;
    }
    EvalsPanel #evals-empty {
        height: 1fr;
        padding: 2 4;
        content-align: center middle;
        text-align: center;
    }
    EvalsPanel #evals-empty.-hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("slash", "begin_search", "Search", show=False),
        Binding("f", "open_filter", "Filter", show=False),
        Binding("s", "open_sort", "Sort", show=False),
        Binding("enter", "open_focused", "Open", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "cursor_first", "First", show=False),
        Binding("G", "cursor_last", "Last", show=False),
        Binding("y", "yank_focused", "Yank id", show=False),
        Binding("d", "next_dataset", "Next dataset", show=False),
        Binding("D", "prev_dataset", "Prev dataset", show=False),
    ]

    SEARCH_DEBOUNCE = 0.2

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        experiment_id: str,
        experiment_name: str | None = None,
        group_name: str | None = None,
        page_size: int = PAGE_SIZE,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._experiment_id = experiment_id
        self._experiment_name = experiment_name
        self._group_name = group_name
        self._page_size = page_size
        # Sort + paging state.
        self._sort_by: str = "created_at"
        self._order: str = SortOrder.DESC.value
        self._search: str | None = None
        self._filter: str | None = None
        self._cursor: str | None = None
        self._has_more: bool = False
        self._loading: bool = False
        # Data + cached column info.
        self._rows: list[_EvalRow] = []
        self._dataset_ids: list[str] = []
        self._selected_dataset: str | None = None  # None == all datasets.
        self._columns: EvalColumns | None = None
        self._average_scores: dict[str, float] = {}
        self._score_ranges: dict[str, tuple[float, float]] = {}
        # Headers placed in the table — keyed by their column id so we
        # can rebuild on dataset switch.
        self._column_order: list[tuple[str, str]] = []
        self._search_timer: Any = None
        # Lazy-load on tab activation.
        self._started: bool = False

    # ----- composition -----

    def compose(self) -> Iterable:
        with Container():
            with Horizontal(id="evals-controls"):
                yield ListView(id="evals-dataset-list")
                with Vertical(id="evals-controls-right"):
                    yield Input(
                        placeholder="Search evals (Esc to close)",
                        id="evals-search",
                    )
                    yield Static(self._format_sort_status(), id="evals-sort-status")
                    yield Static(
                        "", id="evals-filter-status", classes="-empty"
                    )
                    yield Static(
                        "", id="evals-avg-scores", classes="-empty"
                    )
            with Vertical():
                yield Static(self._empty_state_text(), id="evals-empty")
                yield DataTable(
                    id="evals-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )

    def on_mount(self) -> None:
        # Seed `_column_order` with the structural columns so the table
        # has a stable shape before `EvalColumns` arrives — row rendering
        # then never sees an empty column order. The full dynamic set
        # replaces this once `_rebuild_columns` runs.
        self._column_order = [
            ("__id__", "Eval id"),
            ("__dataset__", "Dataset"),
            ("__annotations__", "Annot."),
            ("__created__", "Created"),
        ]
        # The DataTable child may not yet be mounted when `on_mount`
        # fires on the parent widget; defer setup to the next refresh
        # cycle if so.
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            self.call_after_refresh(self._init_table)
        else:
            for _, label in self._column_order:
                table.add_column(label)
        self._update_empty_state()

    def _init_table(self) -> None:
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        if not table.columns:
            for _, label in self._column_order:
                table.add_column(label)
        self._update_empty_state()

    # ----- public lifecycle -----

    def start(self) -> None:
        """Trigger the first dataset list + columns + page fetch.

        The four fetches run concurrently on worker threads; rendering
        gates on whichever finish first (placeholder columns are seeded
        in `on_mount` so the table renders before columns return).
        """

        if self._started or self.facade is None:
            return
        self._started = True
        self._fetch_dataset_ids()
        self._fetch_columns()
        self._fetch_average_scores()
        self.load_first_page()

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        app = self.app
        return getattr(app, "_facade", None)

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- datasets -----

    @work(thread=True, exclusive=True, group="evals-datasets")
    def _fetch_dataset_ids(self) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.get_eval_dataset_ids(self._experiment_id)
        self.app.call_from_thread(self._on_dataset_ids_result, result)

    def _on_dataset_ids_result(self, result: Result[Any]) -> None:
        if not result.ok:
            self._dataset_ids = []
            self._refresh_dataset_list()
            return
        ids = list(result.unwrap() or [])
        self._dataset_ids = ids
        self._refresh_dataset_list()

    def _refresh_dataset_list(self) -> None:
        try:
            view = self.query_one("#evals-dataset-list", ListView)
        except Exception:
            return
        view.clear()
        view.append(
            ListItem(Static("All datasets"), id=f"ds-item-{ALL_DATASETS}")
        )
        for ds in self._dataset_ids:
            view.append(
                ListItem(Static(ds), id=self._dataset_item_id(ds))
            )
        # Keep the selected entry highlighted (default: all).
        view.index = self._selected_dataset_index()

    def _selected_dataset_index(self) -> int:
        if self._selected_dataset is None:
            return 0
        try:
            return self._dataset_ids.index(self._selected_dataset) + 1
        except ValueError:
            return 0

    @staticmethod
    def _dataset_item_id(ds: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in ds)
        return f"ds-item-{safe}"

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "evals-dataset-list" or event.item is None:
            return
        item_id = event.item.id or ""
        if item_id == f"ds-item-{ALL_DATASETS}":
            new_dataset: str | None = None
        else:
            try:
                index = event.list_view.index or 0
            except Exception:
                return
            # index 0 == all, 1..N == dataset
            dataset_index = index - 1
            if not (0 <= dataset_index < len(self._dataset_ids)):
                return
            new_dataset = self._dataset_ids[dataset_index]
        if new_dataset == self._selected_dataset:
            return
        self._selected_dataset = new_dataset
        # Switching datasets changes the column set, the page, and the
        # averages — refetch all three.
        self._fetch_columns()
        self.load_first_page()
        self._fetch_average_scores()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Enter on the list also confirms the dataset.
        self.on_list_view_highlighted(
            ListView.Highlighted(event.list_view, event.item)
        )

    def action_next_dataset(self) -> None:
        self._step_dataset(1)

    def action_prev_dataset(self) -> None:
        self._step_dataset(-1)

    def _step_dataset(self, step: int) -> None:
        """Cycle the dataset selection without leaving the table.

        The keyboard path — there is no focus route to the dataset
        ListView (Tab cycles the screen's tabs). Moving the ListView
        index funnels through `on_list_view_highlighted`, so key and
        mouse selection share one code path.
        """

        if not self._dataset_ids:
            return
        count = len(self._dataset_ids) + 1  # +1 for "All datasets"
        index = (self._selected_dataset_index() + step) % count
        try:
            view = self.query_one("#evals-dataset-list", ListView)
        except Exception:
            return
        view.index = index

    # ----- columns -----

    @work(thread=True, exclusive=True, group="evals-columns")
    def _fetch_columns(self) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.get_eval_columns(
            self._experiment_id, dataset_id=self._selected_dataset
        )
        self.app.call_from_thread(self._on_columns_result, result)

    def _on_columns_result(self, result: Result[Any]) -> None:
        if not result.ok:
            self._columns = None
            return
        self._columns = result.unwrap()
        self._rebuild_columns()
        # After columns change, repopulate the visible rows so they fit.
        self._rerender_rows()

    def _rebuild_columns(self) -> None:
        """Recreate the table columns from the cached `EvalColumns`."""

        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        table.clear(columns=True)
        order: list[tuple[str, str]] = [
            ("__id__", "Eval id"),
            ("__dataset__", "Dataset"),
        ]
        cols = self._columns
        if cols is not None:
            for k in cols.inputs:
                order.append((f"input.{k}", f"in:{k}"))
            for k in cols.outputs:
                order.append((f"output.{k}", f"out:{k}"))
            for k in cols.refs:
                order.append((f"ref.{k}", f"ref:{k}"))
            for k in cols.scores:
                order.append((f"score.{k}", f"score:{k}"))
            for k in cols.metadata:
                order.append((f"metadata.{k}", f"meta:{k}"))
        order.append(("__annotations__", "Annot."))
        order.append(("__created__", "Created"))
        self._column_order = order
        for _, label in order:
            table.add_column(label)

    def _rerender_rows(self) -> None:
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        table.clear()
        for row in self._rows:
            table.add_row(*self._render_row_cells(row), key=row.key)
        self._update_empty_state()

    # ----- average scores -----

    @work(thread=True, exclusive=True, group="evals-averages")
    def _fetch_average_scores(self) -> None:
        facade = self.facade
        if facade is None:
            return
        filters = [self._filter] if self._filter else None
        result = facade.get_eval_average_scores(
            self._experiment_id,
            dataset_id=self._selected_dataset,
            search=self._search or None,
            filters=filters,
        )
        self.app.call_from_thread(self._on_averages_result, result)

    def _on_averages_result(self, result: Result[Any]) -> None:
        if not result.ok:
            self._average_scores = {}
            self._refresh_average_label()
            return
        averages = dict(result.unwrap() or {})
        self._average_scores = averages
        self._refresh_average_label()

    def _refresh_average_label(self) -> None:
        try:
            label = self.query_one("#evals-avg-scores", Static)
        except Exception:
            return
        if not self._average_scores:
            label.update("")
            label.add_class("-empty")
            return
        parts: list[str] = []
        for k in sorted(self._average_scores):
            parts.append(f"{k}: {_format_score(self._average_scores[k])}")
        label.update("avg · " + "  ".join(parts))
        label.remove_class("-empty")

    # ----- pagination -----

    def load_first_page(self) -> None:
        self._cursor = None
        self._has_more = False
        self._rows = []
        try:
            table = self.query_one("#evals-table", DataTable)
            table.clear()
        except Exception:
            pass
        self._set_loading(True)
        self._fetch_page(reset=True)

    def load_next_page(self) -> None:
        if not self._has_more or self._loading:
            return
        self._set_loading(True)
        self._fetch_page(reset=False)

    @work(thread=True, exclusive=True, group="evals-fetch")
    def _fetch_page(self, *, reset: bool) -> None:
        facade = self.facade
        if facade is None:
            self.app.call_from_thread(
                self._on_page_failure, "facade unavailable", reset
            )
            return
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        filters = [self._filter] if self._filter else None
        result = facade.list_evals(
            self._experiment_id,
            limit=self._page_size,
            cursor=None if reset else self._cursor,
            sort_by=self._sort_by,
            order=order,
            dataset_id=self._selected_dataset,
            search=self._search or None,
            filters=filters,
        )
        self.app.call_from_thread(self._on_page_result, result, reset)

    def _on_page_result(self, result: Result[Any], reset: bool) -> None:
        self._set_loading(False)
        if not result.ok:
            message = result.error.message if result.error else "error"
            self._on_page_failure(message, reset)
            return
        page = result.unwrap()
        new_rows = [_EvalRow(key=e.id, eval=e) for e in page.items]
        self._rows = self._rows + new_rows if not reset else new_rows
        self._cursor = page.cursor
        self._has_more = page.cursor is not None and len(page.items) >= self._page_size
        self._recompute_score_ranges()
        self._refresh_table_after_page(new_rows, reset=reset)

    def _on_page_failure(self, message: str, _reset: bool) -> None:
        self._set_loading(False)
        self._lumlflow_app.show_toast(
            f"Could not load evals: {message}", severity="error"
        )

    def _refresh_table_after_page(
        self, new_rows: list[_EvalRow], *, reset: bool
    ) -> None:
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        if reset:
            table.clear()
            for row in self._rows:
                table.add_row(*self._render_row_cells(row), key=row.key)
        else:
            for row in new_rows:
                table.add_row(*self._render_row_cells(row), key=row.key)
        self._update_empty_state()
        self._update_sort_status()
        self._update_filter_status()

    def _update_empty_state(self) -> None:
        try:
            empty = self.query_one("#evals-empty", Static)
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        if not self._rows:
            empty.update(self._empty_state_text())
            empty.remove_class("-hidden")
            table.display = False
        else:
            empty.add_class("-hidden")
            table.display = True

    def _empty_state_text(self) -> str:
        if self._search or self._filter:
            return "No evals match the search/filter."
        if self._selected_dataset is not None:
            return f"No evals in dataset {self._selected_dataset!r}."
        return "No evals yet."

    # ----- row rendering / heatmap -----

    def _recompute_score_ranges(self) -> None:
        """Recompute per-score (low, high) over the currently loaded rows.

        The handler's `average_scores` only gives the mean, so we walk the
        loaded rows once to find min/max per numeric score key. Scores
        with no numeric values get no entry; cells fall back to a plain
        style in that case.
        """

        ranges: dict[str, list[float]] = {}
        for row in self._rows:
            scores = row.eval.scores or {}
            for k, v in scores.items():
                numeric = _numeric_score(v)
                if numeric is None:
                    continue
                ranges.setdefault(k, []).append(numeric)
        self._score_ranges = {
            k: (min(values), max(values)) for k, values in ranges.items()
        }

    def _render_row_cells(self, row: _EvalRow) -> list[Text]:
        eval_rec = row.eval
        cells: list[Text] = []
        for col_id, _ in self._column_order:
            if col_id == "__id__":
                cells.append(Text(eval_rec.id[:12]))
            elif col_id == "__dataset__":
                cells.append(Text(eval_rec.dataset_id, style="dim"))
            elif col_id == "__created__":
                cells.append(
                    Text(eval_rec.created_at.strftime("%Y-%m-%d %H:%M"), style="dim")
                )
            elif col_id == "__annotations__":
                cells.append(self._format_annotation_summary(row.eval))
            elif col_id.startswith("score."):
                key = col_id.split(".", 1)[1]
                value = (eval_rec.scores or {}).get(key)
                cells.append(self._render_score_cell(key, value))
            elif col_id.startswith("input."):
                key = col_id.split(".", 1)[1]
                value = (eval_rec.inputs or {}).get(key)
                cells.append(Text(_format_cell(value), overflow="ellipsis"))
            elif col_id.startswith("output."):
                key = col_id.split(".", 1)[1]
                value = (eval_rec.outputs or {}).get(key)
                cells.append(Text(_format_cell(value), overflow="ellipsis"))
            elif col_id.startswith("ref."):
                key = col_id.split(".", 1)[1]
                value = (eval_rec.refs or {}).get(key)
                cells.append(Text(_format_cell(value), overflow="ellipsis"))
            elif col_id.startswith("metadata."):
                key = col_id.split(".", 1)[1]
                value = (eval_rec.metadata or {}).get(key)
                cells.append(Text(_format_cell(value), overflow="ellipsis"))
            else:
                cells.append(Text("—", style="dim"))
        return cells

    def _render_score_cell(self, key: str, value: Any) -> Text:
        if value is None:
            return Text("—", style="dim")
        numeric = _numeric_score(value)
        if numeric is None:
            return Text(_format_cell(value))
        rng = self._score_ranges.get(key)
        if rng is None:
            return Text(_format_score(numeric))
        low, high = rng
        style = _heatmap_style(numeric, low, high)
        return Text(_format_score(numeric), style=style)

    @staticmethod
    def _format_annotation_summary(eval_rec: Eval) -> Text:
        summary = eval_rec.annotations
        if summary is None:
            return Text("—", style="dim")
        total_fb = sum(item.total for item in summary.feedback)
        total_exp = sum(item.total for item in summary.expectations)
        if total_fb == 0 and total_exp == 0:
            return Text("—", style="dim")
        parts: list[str] = []
        if total_fb:
            parts.append(f"fb {total_fb}")
        if total_exp:
            parts.append(f"exp {total_exp}")
        return Text(" · ".join(parts), style="bold yellow")

    # ----- selection / drill-in -----

    def _focused_row(self) -> _EvalRow | None:
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return None
        if table.row_count == 0:
            return None
        try:
            row_index = table.cursor_row
            if not (0 <= row_index < len(self._rows)):
                return None
            return self._rows[row_index]
        except Exception:
            return None

    def action_open_focused(self) -> None:
        row = self._focused_row()
        if row is None:
            return
        from lumlflow.tui.screens.eval_detail import EvalDetailScreen

        screen = EvalDetailScreen(
            facade=self.facade,
            experiment_id=self._experiment_id,
            experiment_name=self._experiment_name,
            group_name=self._group_name,
            dataset_id=row.eval.dataset_id,
            eval_id=row.key,
        )
        # Cursor/scroll survive the round-trip because this panel stays
        # alive in Textual's stack while the child screen is on top.
        self._lumlflow_app.push_screen(screen)

    def action_cursor_down(self) -> None:
        try:
            self.query_one("#evals-table", DataTable).action_cursor_down()
        except Exception:
            return

    def action_cursor_up(self) -> None:
        try:
            self.query_one("#evals-table", DataTable).action_cursor_up()
        except Exception:
            return

    def action_cursor_first(self) -> None:
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        if table.row_count == 0:
            return
        table.move_cursor(row=0)

    def action_cursor_last(self) -> None:
        try:
            table = self.query_one("#evals-table", DataTable)
        except Exception:
            return
        if table.row_count == 0:
            return
        table.move_cursor(row=table.row_count - 1)

    def action_yank_focused(self) -> None:
        row = self._focused_row()
        if row is None:
            return
        self._lumlflow_app.yank_to_clipboard(row.key, label="eval id")

    # ----- search -----

    def action_begin_search(self) -> None:
        try:
            search = self.query_one("#evals-search", Input)
        except Exception:
            return
        search.add_class("-visible")
        search.value = self._search or ""
        search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "evals-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(
            self.SEARCH_DEBOUNCE, lambda: self._apply_search(event.value)
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "evals-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._apply_search(event.value)
        try:
            self.query_one("#evals-table", DataTable).focus()
        except Exception:
            pass

    def _apply_search(self, value: str) -> None:
        new_search = value.strip() or None
        if new_search == self._search:
            return
        self._search = new_search
        self.load_first_page()
        self._fetch_average_scores()

    def _close_search_if_open(self) -> bool:
        try:
            search = self.query_one("#evals-search", Input)
        except Exception:
            return False
        if "-visible" not in search.classes:
            return False
        search.remove_class("-visible")
        had_search = self._search is not None
        search.value = ""
        self._search = None
        try:
            self.query_one("#evals-table", DataTable).focus()
        except Exception:
            pass
        if had_search:
            self.load_first_page()
            self._fetch_average_scores()
        return True

    def on_key(self, event) -> None:
        if event.key != "escape":
            return
        focused = self.app.focused if self.app is not None else None
        if focused is None:
            return
        if not isinstance(focused, Input) or focused.id != "evals-search":
            return
        if self._close_search_if_open():
            event.stop()

    # ----- filter -----

    def action_open_filter(self) -> None:
        facade = self.facade
        if facade is None:
            self._lumlflow_app.show_toast(
                "Filter editor unavailable (no facade).", severity="error"
            )
            return

        def validator(query: str | None) -> FilterValidation:
            if query is None:
                return FilterValidation(valid=True)
            result = facade.validate_evals_filter([query])
            if not result.ok:
                err = result.error
                return FilterValidation(
                    valid=False, error=err.message if err else "validation failed"
                )
            schema_list = result.unwrap()
            if not schema_list:
                return FilterValidation(valid=True)
            head = schema_list[0]
            return FilterValidation(valid=head.valid, error=head.error)

        dialog = FilterEditorDialog(
            title="Filter evals",
            initial_value=self._filter,
            validator=validator,
            help_text=(
                "Examples:  "
                'dataset_id = "ds-1"  ·  '
                "score.accuracy > 0.8  ·  "
                'input.prompt CONTAINS "hello"'
            ),
        )
        self.app.push_screen(dialog, callback=self._apply_filter_result)

    def _apply_filter_result(self, result: str | None) -> None:
        if result == self._filter:
            return
        self._filter = result
        self.load_first_page()
        self._fetch_average_scores()

    # ----- sort -----

    def action_open_sort(self) -> None:
        dialog = SortChooserDialog(
            title="Sort evals",
            fields=_SORT_FIELDS,
            current_field=self._sort_by,
            current_order=self._order,
        )
        self.app.push_screen(dialog, callback=self._apply_sort_result)

    def _apply_sort_result(self, result: SortChooserResult | None) -> None:
        if result is None:
            return
        if result.field == self._sort_by and result.order == self._order:
            return
        self._sort_by = result.field
        self._order = result.order
        self.load_first_page()

    def _format_sort_status(self) -> str:
        label_by_id = {fid: label for fid, label in _SORT_FIELDS}
        field_label = label_by_id.get(self._sort_by, self._sort_by)
        arrow = "↓" if self._order == "desc" else "↑"
        search_part = (
            f" · search {self._search!r}" if self._search is not None else ""
        )
        ds_part = (
            f" · dataset {self._selected_dataset!r}"
            if self._selected_dataset is not None
            else ""
        )
        return f"sort: {field_label} {arrow}{ds_part}{search_part}"

    def _update_sort_status(self) -> None:
        try:
            self.query_one("#evals-sort-status", Static).update(
                self._format_sort_status()
            )
        except Exception:
            pass

    def _update_filter_status(self) -> None:
        try:
            status = self.query_one("#evals-filter-status", Static)
        except Exception:
            return
        if self._filter:
            status.update(f"filter: {self._filter}  (press [f] to edit)")
            status.remove_class("-empty")
        else:
            status.update("")
            status.add_class("-empty")

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        # DataTable consumes Enter via its own `select_cursor` binding,
        # so the panel-level `Binding("enter", "open_focused")` never
        # fires while the table is focused. Routing through `RowSelected`
        # makes Enter drill into the eval detail uniformly.
        if event.data_table.id != "evals-table":
            return
        self.action_open_focused()

    # ----- lazy pagination -----

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ) -> None:
        if not self._has_more or self._loading:
            return
        prefetch_threshold = 5
        if len(self._rows) <= prefetch_threshold:
            return
        if event.cursor_row >= len(self._rows) - prefetch_threshold:
            self.load_next_page()

    # ----- loading -----

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._lumlflow_app.set_loading(loading)

    # ----- live refresh -----

    def refresh_live(self) -> None:
        """Re-fetch the visible window without disturbing cursor/scroll."""

        if not self._started or self._loading or self.facade is None:
            return
        visible = max(self._page_size, len(self._rows))
        self._refresh_visible_window(limit=visible)

    @work(thread=True, exclusive=True, group="evals-refresh")
    def _refresh_visible_window(self, *, limit: int) -> None:
        facade = self.facade
        if facade is None:
            return
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        filters = [self._filter] if self._filter else None
        result = facade.list_evals(
            self._experiment_id,
            limit=limit,
            cursor=None,
            sort_by=self._sort_by,
            order=order,
            dataset_id=self._selected_dataset,
            search=self._search or None,
            filters=filters,
        )
        self.app.call_from_thread(self._on_refresh_result, result)

    def _on_refresh_result(self, result: Result[Any]) -> None:
        if not result.ok:
            return
        page = result.unwrap()
        new_rows = [_EvalRow(key=e.id, eval=e) for e in page.items]
        self._apply_diff(new_rows)

    def _apply_diff(self, new_rows: list[_EvalRow]) -> None:
        old_by_key = {r.key: r for r in self._rows}
        new_by_key = {r.key: r for r in new_rows}
        removed = [k for k in old_by_key if k not in new_by_key]
        added: list[str] = []
        updated: list[str] = []
        for row in new_rows:
            if row.key not in old_by_key:
                added.append(row.key)
            elif self._row_differs(old_by_key[row.key], row):
                updated.append(row.key)
        if not (removed or added or updated):
            return
        try:
            table = self.query_one("#evals-table", DataTable)
            saved_cursor = table.cursor_row
        except Exception:
            table = None
            saved_cursor = 0
        self._rows = new_rows
        self._recompute_score_ranges()
        if table is not None:
            table.clear()
            for row in new_rows:
                table.add_row(*self._render_row_cells(row), key=row.key)
            if table.row_count > 0:
                clamped = max(0, min(saved_cursor, table.row_count - 1))
                table.move_cursor(row=clamped, animate=False)
            self._pulse_changed_rows(table, added + updated)
        self._update_empty_state()
        self._update_sort_status()
        self._update_filter_status()

    @staticmethod
    def _row_differs(a: _EvalRow, b: _EvalRow) -> bool:
        # Eval scores / outputs / refs are the values that move during
        # a live run; compare them via the schema's dict representation
        # so we catch nested changes without writing field-by-field.
        ae, be = a.eval, b.eval
        return (
            ae.scores != be.scores
            or ae.outputs != be.outputs
            or ae.refs != be.refs
            or ae.metadata != be.metadata
        )

    def _pulse_changed_rows(
        self, table: DataTable, changed_keys: list[str]
    ) -> None:
        if not changed_keys:
            return
        pulse_style = "reverse"
        original_cells: dict[str, Text] = {}
        try:
            first_col = next(iter(table.ordered_columns), None)
        except Exception:
            return
        if first_col is None:
            return
        for key in changed_keys:
            try:
                cell = table.get_cell(key, first_col.key)
            except Exception:
                continue
            if isinstance(cell, Text):
                original_cells[key] = cell.copy()
                pulsed = cell.copy()
                pulsed.stylize(pulse_style)
                table.update_cell(key, first_col.key, pulsed)

        def restore() -> None:
            for key, original in original_cells.items():
                try:
                    table.update_cell(key, first_col.key, original)
                except Exception:
                    pass

        self.set_timer(0.4, restore)


__all__ = (
    "ALL_DATASETS",
    "EvalsPanel",
    "_format_score",
    "_heatmap_style",
    "_numeric_score",
)
