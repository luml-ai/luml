"""TracesPanel widget — the body of the Traces tab.

Renders a paginated traces table for one experiment, with the same
interaction contract every list-screen uses: `/` for incremental
search, `f` for the advanced filter DSL (live-validated against the
handler's `validate_traces_filter`), `s` for sort chooser, `Enter` to
open the trace detail screen, `j`/`k` navigation, lazy pagination.

Trace state colour-coding follows the SPEC: `ok` green, `error` red,
`in_progress` orange (with a clock indicator), `unspecified` dim.

The widget lives inside the experiment detail screen's traces pane;
it owns its own state (cursor, search, filter, sort) but defers
breadcrumb / footer wiring to the parent screen.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    Trace,
    TracesSortBy,
    TraceState,
)
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

_SORT_FIELDS: list[tuple[str, str]] = [
    ("execution_time", "Execution time"),
    ("span_count", "Span count"),
    ("created_at", "Created"),
]

_STATE_COLOR_VAR: dict[TraceState, str] = {
    TraceState.OK: "$state-ok",
    TraceState.ERROR: "$state-error",
    TraceState.IN_PROGRESS: "$state-in-progress",
    TraceState.STATE_UNSPECIFIED: "$state-unspecified",
}

_STATE_LABEL: dict[TraceState, str] = {
    TraceState.OK: "ok",
    TraceState.ERROR: "error",
    TraceState.IN_PROGRESS: "in progress",
    TraceState.STATE_UNSPECIFIED: "unspecified",
}


def _format_execution_time(value_ns: float) -> str:
    """Format `execution_time` (which the schema reports in nanoseconds)."""

    if value_ns <= 0:
        return "—"
    if value_ns < 1_000:
        return f"{value_ns:.0f} ns"
    if value_ns < 1_000_000:
        return f"{value_ns / 1_000:.1f} µs"
    if value_ns < 1_000_000_000:
        return f"{value_ns / 1_000_000:.1f} ms"
    seconds = value_ns / 1_000_000_000
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, sec = divmod(int(seconds), 60)
    return f"{minutes}m {sec:02d}s"


@dataclass
class _TraceRow:
    key: str
    trace: Trace


class TracesPanel(Widget):
    """Lazy-paginated traces list for one experiment.

    Owned by the experiment detail screen. The panel manages its own
    search/filter/sort/pagination state and surfaces row-level actions
    (open detail, yank id) to the parent.
    """

    DEFAULT_CSS = """
    TracesPanel {
        layout: vertical;
        height: 1fr;
    }
    TracesPanel #traces-search {
        margin: 0 2;
        display: none;
    }
    TracesPanel #traces-search.-visible {
        display: block;
    }
    TracesPanel #traces-sort-status {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    TracesPanel #traces-filter-status {
        height: 1;
        padding: 0 2;
        color: $warning;
    }
    TracesPanel #traces-filter-status.-empty {
        display: none;
    }
    TracesPanel #traces-table {
        height: 1fr;
    }
    TracesPanel #traces-empty {
        height: 1fr;
        padding: 2 4;
        content-align: center middle;
        text-align: center;
    }
    TracesPanel #traces-empty.-hidden {
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
        self._sort_by: str = TracesSortBy.EXECUTION_TIME.value
        self._order: str = SortOrder.DESC.value
        self._search: str | None = None
        self._filter: str | None = None
        self._cursor: str | None = None
        self._has_more: bool = False
        self._loading: bool = False
        self._rows: list[_TraceRow] = []
        self._search_timer: Any = None
        # The first time the user navigates to the tab the panel mounts
        # but the parent screen may not yet have data — the panel waits
        # for `start()` so screens can control when the first page loads.
        self._started: bool = False

    # ----- composition -----

    def compose(self) -> Iterable:
        with Container():
            yield Input(
                placeholder="Search traces (Esc to close)",
                id="traces-search",
            )
            yield Static(self._format_sort_status(), id="traces-sort-status")
            yield Static(
                "", id="traces-filter-status", classes="-empty"
            )
            with Vertical():
                yield Static(self._empty_state_text(), id="traces-empty")
                yield DataTable(
                    id="traces-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )

    def on_mount(self) -> None:
        table = self.query_one("#traces-table", DataTable)
        table.add_columns(
            "Trace id", "State", "Duration", "Spans", "Annotations", "Created"
        )
        self._update_empty_state()

    # ----- public lifecycle -----

    def start(self) -> None:
        """Trigger the first page fetch.

        The panel does not load on mount because the traces pane may
        not be visible yet — the parent screen calls `start()` when the
        user actually opens the tab, so we don't pay the read cost on
        every detail screen open.
        """

        if self._started or self.facade is None:
            return
        self._started = True
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

    # ----- pagination -----

    def load_first_page(self) -> None:
        self._cursor = None
        self._has_more = False
        self._rows = []
        try:
            table = self.query_one("#traces-table", DataTable)
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

    @work(thread=True, exclusive=True, group="traces-fetch")
    def _fetch_page(self, *, reset: bool) -> None:
        facade = self.facade
        if facade is None:
            self.app.call_from_thread(
                self._on_page_failure, "facade unavailable", reset
            )
            return
        try:
            sort_by = TracesSortBy(self._sort_by)
        except ValueError:
            sort_by = TracesSortBy.EXECUTION_TIME
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        filters = [self._filter] if self._filter else None
        result = facade.list_traces(
            self._experiment_id,
            limit=self._page_size,
            cursor=None if reset else self._cursor,
            sort_by=sort_by,
            order=order,
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
        new_rows = [_TraceRow(key=t.trace_id, trace=t) for t in page.items]
        self._rows = self._rows + new_rows if not reset else new_rows
        self._cursor = page.cursor
        self._has_more = page.cursor is not None and len(page.items) >= self._page_size
        self._refresh_table_after_page(new_rows, reset=reset)

    def _on_page_failure(self, message: str, _reset: bool) -> None:
        self._set_loading(False)
        self._lumlflow_app.show_toast(
            f"Could not load traces: {message}", severity="error"
        )

    def _refresh_table_after_page(
        self, new_rows: list[_TraceRow], *, reset: bool
    ) -> None:
        try:
            table = self.query_one("#traces-table", DataTable)
        except Exception:
            return
        if reset:
            table.clear()
        for row in new_rows:
            table.add_row(*self._render_row_cells(row), key=row.key)
        self._update_empty_state()
        self._update_sort_status()
        self._update_filter_status()

    def _update_empty_state(self) -> None:
        try:
            empty = self.query_one("#traces-empty", Static)
            table = self.query_one("#traces-table", DataTable)
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
            return "No traces match the search/filter."
        return "No traces yet."

    # ----- row rendering -----

    def _render_row_cells(
        self, row: _TraceRow
    ) -> tuple[Text, Text, Text, Text, Text, Text]:
        trace = row.trace
        state_color = _STATE_COLOR_VAR.get(trace.state, "$state-unspecified")
        state_label = _STATE_LABEL.get(trace.state, "unspecified")
        prefix = ""
        if trace.state == TraceState.IN_PROGRESS:
            prefix = "⟳ "
        elif trace.state == TraceState.ERROR:
            prefix = "✗ "
        elif trace.state == TraceState.OK:
            prefix = "✓ "
        state = Text(f"{prefix}{state_label}", style=f"bold {state_color}")
        # Short id for the table; the full id is reachable via yank.
        short_id = trace.trace_id[:12]
        if trace.state == TraceState.ERROR:
            id_text = Text(short_id, style="bold")
        else:
            id_text = Text(short_id)
        duration = Text(
            _format_execution_time(trace.execution_time), style="dim"
        )
        spans = Text(str(trace.span_count), style="dim")
        annotations = self._format_annotation_summary(trace)
        created = Text(
            trace.created_at.strftime("%Y-%m-%d %H:%M"), style="dim"
        )
        return id_text, state, duration, spans, annotations, created

    @staticmethod
    def _format_annotation_summary(trace: Trace) -> Text:
        summary = trace.annotations
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

    def _focused_row(self) -> _TraceRow | None:
        try:
            table = self.query_one("#traces-table", DataTable)
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
        from lumlflow.tui.screens.trace_detail import TraceDetailScreen

        screen = TraceDetailScreen(
            facade=self.facade,
            experiment_id=self._experiment_id,
            experiment_name=self._experiment_name,
            group_name=self._group_name,
            trace_id=row.key,
        )
        # Cursor/scroll survive the round-trip because this panel stays
        # alive in Textual's stack while the child screen is on top.
        self._lumlflow_app.push_screen(screen)

    def action_cursor_down(self) -> None:
        try:
            self.query_one("#traces-table", DataTable).action_cursor_down()
        except Exception:
            return

    def action_cursor_up(self) -> None:
        try:
            self.query_one("#traces-table", DataTable).action_cursor_up()
        except Exception:
            return

    def action_cursor_first(self) -> None:
        try:
            table = self.query_one("#traces-table", DataTable)
        except Exception:
            return
        if table.row_count == 0:
            return
        table.move_cursor(row=0)

    def action_cursor_last(self) -> None:
        try:
            table = self.query_one("#traces-table", DataTable)
        except Exception:
            return
        if table.row_count == 0:
            return
        table.move_cursor(row=table.row_count - 1)

    def action_yank_focused(self) -> None:
        row = self._focused_row()
        if row is None:
            return
        self._lumlflow_app.yank_to_clipboard(row.key, label="trace id")

    # ----- search -----

    def action_begin_search(self) -> None:
        try:
            search = self.query_one("#traces-search", Input)
        except Exception:
            return
        search.add_class("-visible")
        search.value = self._search or ""
        search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "traces-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(
            self.SEARCH_DEBOUNCE, lambda: self._apply_search(event.value)
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "traces-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._apply_search(event.value)
        try:
            self.query_one("#traces-table", DataTable).focus()
        except Exception:
            pass

    def _apply_search(self, value: str) -> None:
        new_search = value.strip() or None
        if new_search == self._search:
            return
        self._search = new_search
        self.load_first_page()

    def _close_search_if_open(self) -> bool:
        try:
            search = self.query_one("#traces-search", Input)
        except Exception:
            return False
        if "-visible" not in search.classes:
            return False
        search.remove_class("-visible")
        had_search = self._search is not None
        search.value = ""
        self._search = None
        try:
            self.query_one("#traces-table", DataTable).focus()
        except Exception:
            pass
        if had_search:
            self.load_first_page()
        return True

    def on_key(self, event) -> None:
        if event.key != "escape":
            return
        focused = self.app.focused if self.app is not None else None
        if focused is None:
            return
        if not isinstance(focused, Input) or focused.id != "traces-search":
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
            result = facade.validate_traces_filter([query])
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
            title="Filter traces",
            initial_value=self._filter,
            validator=validator,
            help_text=(
                "Examples:  "
                'state = "error"  ·  '
                "span_count > 5  ·  "
                'attributes.user_id = "u-42"'
            ),
        )
        self.app.push_screen(dialog, callback=self._apply_filter_result)

    def _apply_filter_result(self, result: str | None) -> None:
        if result == self._filter:
            return
        self._filter = result
        self.load_first_page()

    # ----- sort -----

    def action_open_sort(self) -> None:
        dialog = SortChooserDialog(
            title="Sort traces",
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
        return f"sort: {field_label} {arrow}{search_part}"

    def _update_sort_status(self) -> None:
        try:
            self.query_one("#traces-sort-status", Static).update(
                self._format_sort_status()
            )
        except Exception:
            pass

    def _update_filter_status(self) -> None:
        try:
            status = self.query_one("#traces-filter-status", Static)
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
        # makes Enter drill into the trace detail uniformly.
        if event.data_table.id != "traces-table":
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
        """Re-fetch the visible window without disturbing cursor/scroll.

        State flips for in-progress traces are the most visible payoff
        here: a row tagged `in_progress` becoming `ok`/`error` re-colours
        without forcing the user to scroll back.
        """

        if not self._started or self._loading or self.facade is None:
            return
        visible = max(self._page_size, len(self._rows))
        self._refresh_visible_window(limit=visible)

    @work(thread=True, exclusive=True, group="traces-refresh")
    def _refresh_visible_window(self, *, limit: int) -> None:
        facade = self.facade
        if facade is None:
            return
        try:
            sort_by = TracesSortBy(self._sort_by)
        except ValueError:
            sort_by = TracesSortBy.EXECUTION_TIME
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        filters = [self._filter] if self._filter else None
        result = facade.list_traces(
            self._experiment_id,
            limit=limit,
            cursor=None,
            sort_by=sort_by,
            order=order,
            search=self._search or None,
            filters=filters,
        )
        self.app.call_from_thread(self._on_refresh_result, result)

    def _on_refresh_result(self, result: Result[Any]) -> None:
        if not result.ok:
            return
        page = result.unwrap()
        new_rows = [_TraceRow(key=t.trace_id, trace=t) for t in page.items]
        self._apply_diff(new_rows)

    def _apply_diff(self, new_rows: list[_TraceRow]) -> None:
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
            table = self.query_one("#traces-table", DataTable)
            saved_cursor = table.cursor_row
        except Exception:
            table = None
            saved_cursor = 0
        self._rows = new_rows
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
    def _row_differs(a: _TraceRow, b: _TraceRow) -> bool:
        return (
            a.trace.state != b.trace.state
            or a.trace.execution_time != b.trace.execution_time
            or a.trace.span_count != b.trace.span_count
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
    "TracesPanel",
    "_format_execution_time",
)
