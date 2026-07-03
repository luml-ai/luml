"""Experiments list screen.

Renders the experiments belonging to a single group, or — when no group
is supplied — every experiment in the store ("All experiments" mode).
Implements the SPEC's interaction contract: `/` for incremental
free-text search, `f` for the advanced filter DSL with live validation,
`s` for sort chooser, `e`/`d` for edit/delete, `Enter` to drill in,
lazy pagination as the user scrolls. Experiment status is rendered
with the semantic palette colours (active/completed/error).

Data is fetched through the `DataFacade` on Textual worker threads so
the event loop never blocks on SQLite — search input is debounced.
The "All experiments" mode first fetches the full list of group ids so
the existing handler (`list_groups_experiments`) can serve a unified
cross-group page using the same cursor pagination.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import DataTable, Input, Static

from lumlflow.schemas.base import SortOrder
from lumlflow.schemas.experiments import (
    ExperimentDetails,
    ExperimentStatus,
    UpdateExperiment,
)
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment, PaletteEntry, PanelFrame
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
    FilterEditorDialog,
    FilterValidation,
    SortChooserDialog,
    SortChooserResult,
)

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp

PAGE_SIZE = 50


# Allowed sort fields. The handler accepts arbitrary `sort_by` strings
# resolved via `resolve_*_sort_column`; for the UI chooser we list the
# common standard columns. Static/dynamic param sorts are reachable via
# the API but require knowing the keys, which we surface only after a
# columns fetch (future task).
_SORT_FIELDS: list[tuple[str, str]] = [
    ("created_at", "Created"),
    ("name", "Name"),
    ("duration", "Duration"),
    ("status", "Status"),
]

# Table column label → sortable field, for header-click sorting.
# Sel / Tags / Group columns have no backing sort field.
_HEADER_SORT_FIELDS: dict[str, str] = {
    "Name": "name",
    "Status": "status",
    "Duration": "duration",
    "Created": "created_at",
}


_STATUS_COLOR_VAR: dict[ExperimentStatus, str] = {
    ExperimentStatus.ACTIVE: "$status-active",
    ExperimentStatus.COMPLETED: "$status-completed",
    ExperimentStatus.ERROR: "$status-error",
}


@dataclass
class _ExperimentRow:
    """One row in the experiments table."""

    key: str
    name: str
    status: ExperimentStatus
    duration: float | None
    tags: list[str]
    group_name: str | None
    created_at: str
    raw: ExperimentDetails


def _format_duration(value: float | None) -> str:
    """Format duration (seconds) as a compact label.

    Returns an em dash for unknown durations so the column reads cleanly.
    """

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


def _render_tag_chips(tags: list[str]) -> Text:
    """Render a list of tags as colored chip-style text.

    Wrapping each tag in thin spaces gives it a pill-like appearance
    against the panel background; the color is keyed off the tag string
    so the same tag always uses the same color across screens.
    """

    out = Text()
    for i, tag in enumerate(tags):
        if i > 0:
            out.append(" ")
        color_index = hash(tag) % 8
        out.append(f" {tag} ", style=f"bold $tag-{color_index} on $panel")
    return out


class ExperimentsScreen(BaseScreen):
    """Experiments table for a single group or across all groups.

    Owns the active `sort_by`/`order`/`search`/`filters` state plus the
    pagination cursor; the facade is told what to fetch and the screen
    appends rows. Edits and deletes update the affected row in place.

    Two modes:
    - single-group: `group_id` set, `group_name` shown in breadcrumb
    - all-experiments: `group_id` is `None`, the screen first resolves
      every group id, then issues a cross-group query.
    """

    DEFAULT_CSS = """
    ExperimentsScreen {
        layout: vertical;
    }
    ExperimentsScreen #experiments-body {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    ExperimentsScreen #experiments-search {
        margin: 0 1 1 1;
        display: none;
    }
    ExperimentsScreen #experiments-search.-visible {
        display: block;
    }
    ExperimentsScreen #experiments-panel {
        height: 1fr;
    }
    ExperimentsScreen #experiments-table {
        height: 1fr;
    }
    ExperimentsScreen #experiments-empty {
        height: 1fr;
        padding: 2 4;
        content-align: center middle;
        text-align: center;
        color: $foreground 70%;
    }
    ExperimentsScreen #experiments-empty.-hidden {
        display: none;
    }
    ExperimentsScreen #experiments-loading {
        height: 1;
        padding: 0 1;
        color: $accent;
        display: none;
    }
    ExperimentsScreen #experiments-loading.-visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("slash", "begin_search", "Search", show=False),
        Binding("f", "open_filter", "Filter", show=False),
        Binding("s", "open_sort", "Sort", show=False),
        Binding("e", "edit_focused", "Edit", show=False),
        Binding("d", "delete_focused", "Delete", show=False),
        Binding("y", "yank_focused", "Yank id", show=False),
        Binding("space", "toggle_selection", "Select", show=False),
        Binding("c", "compare_selected", "Compare", show=False),
        Binding("p", "publish_focused", "Publish", show=False),
        Binding("enter", "open_focused", "Open", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "cursor_first", "First", show=False),
        Binding("shift+g", "cursor_last", "Last", show=False),
    ]

    AUTO_FOCUS = "#experiments-table"

    SEARCH_DEBOUNCE = 0.2

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        group_id: str | None = None,
        group_name: str | None = None,
        all_experiments: bool = False,
        page_size: int = PAGE_SIZE,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        if group_id is None and not all_experiments:
            raise ValueError(
                "ExperimentsScreen requires either group_id or all_experiments=True"
            )
        self._facade = facade
        self._group_id = group_id
        self._group_name = group_name
        self._all_experiments = all_experiments
        self._page_size = page_size
        self._sort_by: str = "created_at"
        self._order: str = SortOrder.DESC.value
        self._search: str | None = None
        self._filter: str | None = None
        self._cursor: str | None = None
        self._has_more: bool = False
        self._loading: bool = False
        self._rows: list[_ExperimentRow] = []
        self._search_timer: Any = None
        # Cached list of group ids for the All Experiments mode — fetched
        # lazily on first page so the unified cross-group query is one
        # round-trip rather than two each page.
        self._all_group_ids_cache: list[str] | None = None

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="experiments-body"):
            yield Input(
                placeholder="Search experiments (Esc to close)",
                id="experiments-search",
            )
            with PanelFrame(
                title=self._panel_title(),
                subtitle=self._panel_subtitle(),
                fill=True,
                id="experiments-panel",
            ):
                yield Static("Loading…", id="experiments-loading")
                yield Static(
                    self._empty_state_text(),
                    id="experiments-empty",
                )
                yield DataTable(
                    id="experiments-table",
                    cursor_type="row",
                    zebra_stripes=True,
                )

    def on_mount(self) -> None:
        table = self.query_one("#experiments-table", DataTable)
        table.add_columns(
            "Sel", "Name", "Status", "Duration", "Tags", "Group", "Created"
        )
        self._update_empty_state()
        self._update_panel_subtitle()
        # Sync the header to the cross-screen selection count so users
        # see at a glance how many experiments are queued for comparison.
        try:
            self._lumlflow_app.set_selection_count(
                len(self._lumlflow_app.selected_experiment_ids)
            )
        except Exception:
            pass
        if self.facade is not None:
            self.load_first_page()

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        if self._all_experiments:
            return (
                BreadcrumbSegment("Groups"),
                BreadcrumbSegment("All experiments"),
            )
        label = self._group_name or "Experiments"
        return (
            BreadcrumbSegment("Groups"),
            BreadcrumbSegment(label),
        )

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global", "list", "actions", "selection")

    # ----- facade -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        app = self.app
        prebuilt = getattr(app, "_facade", None)
        return prebuilt

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        return cast("LumlflowApp", self.app)

    # ----- data loading -----

    def load_first_page(self) -> None:
        self._cursor = None
        self._has_more = False
        self._rows = []
        try:
            table = self.query_one("#experiments-table", DataTable)
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

    @work(thread=True, exclusive=True, group="experiments")
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
        if self._all_experiments:
            # Resolve the full set of group ids on the first page; reuse the
            # cache on subsequent pages and after sort/search changes.
            group_ids = self._all_group_ids_cache
            if group_ids is None or reset:
                groups_res = facade.list_groups(limit=1000)
                if not groups_res.ok:
                    message = (
                        groups_res.error.message
                        if groups_res.error
                        else "could not list groups"
                    )
                    self.app.call_from_thread(
                        self._on_page_failure, message, reset
                    )
                    return
                group_ids = [g.id for g in groups_res.unwrap().items]
                self._all_group_ids_cache = group_ids
            if not group_ids:
                # No groups at all → empty result page, no crash.
                from lumlflow.schemas.experiments import PaginatedExperiments

                self.app.call_from_thread(
                    self._on_page_result,
                    Result.success(PaginatedExperiments(items=[], cursor=None)),
                    reset,
                )
                return
            result = facade.list_groups_experiments(
                group_ids,
                limit=self._page_size,
                cursor=None if reset else self._cursor,
                sort_by=self._sort_by,
                order=order,
                search=self._combined_search(),
            )
        else:
            assert self._group_id is not None
            result = facade.list_group_experiments(
                self._group_id,
                limit=self._page_size,
                cursor=None if reset else self._cursor,
                sort_by=self._sort_by,
                order=order,
                search=self._combined_search(),
            )
        self.app.call_from_thread(self._on_page_result, result, reset)

    def _combined_search(self) -> str | None:
        """Combine free-text search with the advanced filter expression.

        The handlers' `search` parameter accepts a DSL expression only —
        bare text doesn't parse. We translate the quick-search query
        into a name/tags LIKE clause so the user can type a fragment
        and see it narrow the list. The advanced filter (`f`) goes
        through verbatim; both are joined with `AND` when set.
        """

        search_dsl = self._free_text_to_dsl(self._search)
        if search_dsl and self._filter:
            return f"({search_dsl}) AND ({self._filter})"
        return search_dsl or self._filter

    @staticmethod
    def _free_text_to_dsl(text: str | None) -> str | None:
        """Wrap a bare search fragment in a name/tags LIKE clause.

        If the user typed something that already looks like a DSL
        expression (contains a comparison or logical operator) we leave
        it alone so power-users can drop into the filter language from
        the quick-search field.
        """

        if not text:
            return None
        dsl_tokens = (
            " = ",
            " != ",
            " > ",
            " < ",
            "LIKE ",
            "ILIKE ",
            "CONTAINS ",
            " IN ",
            " AND ",
            " OR ",
        )
        looks_like_dsl = any(tok in text for tok in dsl_tokens)
        if looks_like_dsl:
            return text
        # Escape any embedded double-quotes so the LIKE literal stays valid.
        safe = text.replace('"', '\\"')
        return f'name LIKE "%{safe}%" OR tags CONTAINS "{safe}"'

    def _on_page_result(self, result: Result[Any], reset: bool) -> None:
        self._set_loading(False)
        if not result.ok:
            message = result.error.message if result.error else "error"
            self._on_page_failure(message, reset)
            return
        page = result.unwrap()
        new_rows = [self._to_row(e) for e in page.items]
        self._rows = self._rows + new_rows if not reset else new_rows
        self._cursor = page.cursor
        self._has_more = page.cursor is not None and len(page.items) >= self._page_size
        self._refresh_table_after_page(new_rows, reset=reset)

    def _on_page_failure(self, message: str, _reset: bool) -> None:
        self._set_loading(False)
        self._lumlflow_app.show_toast(
            f"Could not load experiments: {message}", severity="error"
        )

    def _refresh_table_after_page(
        self, new_rows: list[_ExperimentRow], *, reset: bool
    ) -> None:
        table = self.query_one("#experiments-table", DataTable)
        if reset:
            table.clear()
        for row in new_rows:
            table.add_row(*self._render_row_cells(row), key=row.key)
        self._update_empty_state()
        self._update_panel_subtitle()

    def _update_empty_state(self) -> None:
        empty = self.query_one("#experiments-empty", Static)
        table = self.query_one("#experiments-table", DataTable)
        if not self._rows:
            empty.update(self._empty_state_text())
            empty.remove_class("-hidden")
            table.display = False
        else:
            empty.add_class("-hidden")
            table.display = True
        self._update_panel_subtitle()

    def _empty_state_text(self) -> str:
        if self._search or self._filter:
            return (
                "No experiments match the active search/filter.\n\n"
                "Press [Esc] to clear search or [f] to edit the filter."
            )
        if self._all_experiments:
            return (
                "No experiments yet.\n\n"
                "Experiments appear here as your training scripts log to "
                "this store."
            )
        return (
            f"Group {self._group_name or self._group_id!r} has no "
            "experiments yet.\n\n"
            "Experiments appear here as scripts log to this group."
        )

    # ----- row rendering -----

    def _to_row(self, experiment: ExperimentDetails) -> _ExperimentRow:
        return _ExperimentRow(
            key=experiment.id,
            name=experiment.name,
            status=experiment.status,
            duration=experiment.duration,
            tags=experiment.tags or [],
            group_name=experiment.group_name,
            created_at=experiment.created_at.strftime("%Y-%m-%d %H:%M")
            if experiment.created_at is not None
            else "",
            raw=experiment,
        )

    def _render_row_cells(
        self, row: _ExperimentRow
    ) -> tuple[Text, Text, Text, Text, Text, Text, Text]:
        # Active experiments get extra visual emphasis since they're the
        # live ones (per SPEC's status color contract).
        status_color = _STATUS_COLOR_VAR.get(
            row.status, "$state-unspecified"
        )
        if row.status == ExperimentStatus.ACTIVE:
            name = Text(row.name, style=f"bold {status_color}")
            status = Text(
                f" {row.status.value} ",
                style=f"bold {status_color} on $panel",
            )
        else:
            name = Text(row.name)
            status = Text(
                f" {row.status.value} ", style=f"{status_color} on $panel"
            )
        duration = Text(_format_duration(row.duration), style="dim")
        tags = _render_tag_chips(row.tags)
        group = Text(row.group_name or "—", style="dim")
        created = Text(row.created_at, style="dim")
        selected = self._is_row_selected(row.key)
        # ✓ marks a row queued for comparison; the marker survives
        # navigation since the selection lives on the app.
        sel_marker = (
            Text("✓", style="bold $accent")
            if selected
            else Text(" ", style="dim")
        )
        return sel_marker, name, status, duration, tags, group, created

    def _is_row_selected(self, experiment_id: str) -> bool:
        try:
            return self._lumlflow_app.is_experiment_selected(experiment_id)
        except Exception:
            return False

    # ----- selection / drill-in -----

    def _focused_row(self) -> _ExperimentRow | None:
        table = self.query_one("#experiments-table", DataTable)
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
        from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen

        screen = ExperimentDetailScreen(
            facade=self.facade,
            experiment_id=row.key,
            experiment_name=row.name,
            group_name=row.group_name,
        )
        # Cursor/scroll survive the round-trip because the screen stays
        # alive in Textual's stack while the child is on top.
        self._lumlflow_app.push_screen(screen)

    def action_cursor_down(self) -> None:
        table = self.query_one("#experiments-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#experiments-table", DataTable)
        table.action_cursor_up()

    def action_cursor_first(self) -> None:
        table = self.query_one("#experiments-table", DataTable)
        if table.row_count == 0:
            return
        table.move_cursor(row=0)

    def action_cursor_last(self) -> None:
        table = self.query_one("#experiments-table", DataTable)
        if table.row_count == 0:
            return
        table.move_cursor(row=table.row_count - 1)

    def action_yank_focused(self) -> None:
        row = self._focused_row()
        if row is None:
            return
        self._lumlflow_app.yank_to_clipboard(row.key, label="experiment id")

    # ----- palette jump-to -----

    def palette_entries(self) -> list[PaletteEntry]:
        """Contribute jump-to entries for every currently-loaded experiment.

        Per SPEC the palette is dual-purpose ("jump-to: any screen, or a
        group/experiment by name"); each experiment row becomes a
        palette entry whose `invoke` drills into its detail screen.
        """

        entries: list[PaletteEntry] = []
        for row in self._rows:
            label = row.name
            if row.group_name:
                label = f"{row.name} · {row.group_name}"
            entries.append(
                PaletteEntry(
                    label=label,
                    description=f"status {row.status.value}",
                    kind="experiment",
                    invoke=self._make_jump_invoke(row.key),
                    extra_search=" ".join(row.tags),
                )
            )
        return entries

    def _make_jump_invoke(self, row_key: str):
        def _invoke() -> None:
            for i, row in enumerate(self._rows):
                if row.key == row_key:
                    try:
                        table = self.query_one("#experiments-table", DataTable)
                        table.move_cursor(row=i, animate=False)
                    except Exception:
                        pass
                    self.action_open_focused()
                    return

        return _invoke

    # ----- multi-selection (for comparison) -----

    def action_toggle_selection(self) -> None:
        """Toggle the focused row's membership in the comparison selection."""

        row = self._focused_row()
        if row is None:
            return
        selected = self._lumlflow_app.toggle_experiment_selection(row.raw)
        # Re-render the row's selection-marker cell in place so the
        # change is visible without re-fetching the page.
        try:
            table = self.query_one("#experiments-table", DataTable)
            cells = self._render_row_cells(row)
            first_col = next(iter(table.ordered_columns), None)
            if first_col is not None:
                table.update_cell(row.key, first_col.key, cells[0])
        except Exception:
            pass
        verb = "Added to" if selected else "Removed from"
        self._lumlflow_app.show_toast(
            f"{verb} comparison · {row.name}",
            severity="info",
            duration=1.5,
        )

    def select_all_visible(self) -> None:
        """Add every loaded experiment row to the comparison selection.

        Surfaced as a palette-only action (`selection.select_all`) so
        the user has a one-shot way to gather everything currently in
        view without manually pressing `Space` on each row.
        """

        if not self._rows:
            self._lumlflow_app.show_toast(
                "Nothing to select on this screen.", severity="info", duration=1.5
            )
            return
        added = 0
        for row in self._rows:
            if not self._lumlflow_app.is_experiment_selected(row.key):
                self._lumlflow_app.toggle_experiment_selection(row.raw)
                added += 1
        # Refresh the selection-marker column for every visible row in
        # one go so the change reads at a glance.
        try:
            table = self.query_one("#experiments-table", DataTable)
            first_col = next(iter(table.ordered_columns), None)
            if first_col is not None:
                for row in self._rows:
                    cells = self._render_row_cells(row)
                    table.update_cell(row.key, first_col.key, cells[0])
        except Exception:
            pass
        self._lumlflow_app.show_toast(
            f"Selected {added} for comparison.", severity="info", duration=1.5
        )

    def action_compare_selected(self) -> None:
        """Open the comparison screen with the current selection.

        If only one experiment is selected, the focused row is added so
        the screen never opens with a single-item comparison (per SPEC,
        comparison is across "a selected set"). With zero selection we
        surface a toast pointing at `Space` rather than crashing.
        """

        ids = self._lumlflow_app.selected_experiment_ids
        if len(ids) < 2:
            row = self._focused_row()
            if row is not None and not self._lumlflow_app.is_experiment_selected(
                row.key
            ):
                self._lumlflow_app.toggle_experiment_selection(row.raw)
                ids = self._lumlflow_app.selected_experiment_ids
        if len(ids) < 2:
            self._lumlflow_app.show_toast(
                "Select 2+ experiments with [Space] to compare.",
                severity="warning",
                duration=2.5,
            )
            return
        from lumlflow.tui.screens.comparison import ComparisonScreen

        experiments = list(self._lumlflow_app.selected_experiments.values())
        screen = ComparisonScreen(
            facade=self.facade,
            experiments=experiments,
        )
        self.app.push_screen(screen)

    def action_publish_focused(self) -> None:
        """Open the cloud publish flow against the focused experiment."""

        row = self._focused_row()
        if row is None:
            return
        from lumlflow.tui.screens.cloud_publish import CloudPublishScreen

        screen = CloudPublishScreen(
            facade=self.facade,
            experiment_id=row.key,
            experiment_name=row.name,
            breadcrumb_prefix=self.breadcrumb_segments(),
        )
        self.app.push_screen(screen)

    # ----- search -----

    def action_begin_search(self) -> None:
        search = self.query_one("#experiments-search", Input)
        search.add_class("-visible")
        search.value = self._search or ""
        search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "experiments-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(
            self.SEARCH_DEBOUNCE, lambda: self._apply_search(event.value)
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "experiments-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._apply_search(event.value)
        try:
            self.query_one("#experiments-table", DataTable).focus()
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
            search = self.query_one("#experiments-search", Input)
        except Exception:
            return False
        if "-visible" not in search.classes:
            return False
        search.remove_class("-visible")
        had_search = self._search is not None
        search.value = ""
        self._search = None
        try:
            self.query_one("#experiments-table", DataTable).focus()
        except Exception:
            pass
        if had_search:
            self.load_first_page()
        return True

    def on_key(self, event) -> None:
        if event.key != "escape":
            return
        focused = self.focused
        if focused is None:
            return
        if not isinstance(focused, Input) or focused.id != "experiments-search":
            return
        if self._close_search_if_open():
            event.stop()

    # ----- filter (advanced DSL) -----

    def action_open_filter(self) -> None:
        facade = self.facade
        if facade is None:
            self._lumlflow_app.show_toast(
                "Filter editor unavailable (no facade).", severity="error"
            )
            return

        def validator(query: str | None) -> FilterValidation:
            result = facade.validate_experiments_search(query)
            if not result.ok:
                err = result.error
                return FilterValidation(
                    valid=False, error=err.message if err else "validation failed"
                )
            schema = result.unwrap()
            return FilterValidation(valid=schema.valid, error=schema.error)

        dialog = FilterEditorDialog(
            title="Filter experiments",
            initial_value=self._filter,
            validator=validator,
            help_text=(
                "Advanced filter DSL · examples:  "
                'status = "active"  ·  '
                'tags CONTAINS "prod" AND duration > 60  ·  '
                "metric.accuracy > 0.85"
            ),
        )
        self.app.push_screen(dialog, callback=self._apply_filter_result)

    def _apply_filter_result(self, result: str | None) -> None:
        # `None` from the dialog means "cancelled" — but the dialog also
        # uses `None` for "empty input → clear filter". The dialog
        # always dismisses with the value-or-None on confirm; cancel
        # also dismisses with None. We treat both the same: an empty
        # value cancels the filter, which is a no-op if there wasn't one.
        if result == self._filter:
            return
        self._filter = result
        self.load_first_page()

    # ----- sort -----

    def action_open_sort(self) -> None:
        dialog = SortChooserDialog(
            title="Sort experiments",
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

    def on_data_table_header_selected(
        self, event: DataTable.HeaderSelected
    ) -> None:
        """Clicking a column header sorts by it (click again to flip)."""

        if event.data_table.id != "experiments-table":
            return
        field = _HEADER_SORT_FIELDS.get(str(event.label))
        if field is None:
            return
        if field == self._sort_by:
            order = "asc" if self._order == "desc" else "desc"
        else:
            order = "asc" if field == "name" else "desc"
        self._apply_sort_result(SortChooserResult(field=field, order=order))

    def _format_sort_status(self) -> str:
        label_by_id = {fid: label for fid, label in _SORT_FIELDS}
        field_label = label_by_id.get(self._sort_by, self._sort_by)
        arrow = "↓" if self._order == "desc" else "↑"
        search_part = (
            f" · search {self._search!r}" if self._search is not None else ""
        )
        return f"sort: {field_label} {arrow}{search_part}"

    def _panel_title(self) -> str:
        if self._all_experiments:
            return "All experiments"
        if self._group_name:
            return f"Experiments · {self._group_name}"
        return "Experiments"

    def _panel_subtitle(self) -> str:
        """Right-aligned subtitle: row count + sort + filter chip."""

        count = len(self._rows)
        count_part = f"{count} experiment{'s' if count != 1 else ''}"
        parts = [count_part, self._format_sort_status()]
        if self._filter:
            parts.append(f"filter: {self._filter}")
        return " · ".join(parts)

    def _update_panel_subtitle(self) -> None:
        try:
            panel = self.query_one("#experiments-panel", PanelFrame)
            panel.set_subtitle(self._panel_subtitle())
        except Exception:
            pass

    # ----- edit / delete -----

    def action_edit_focused(self) -> None:
        row = self._focused_row()
        if row is None:
            return
        dialog = EditEntityDialog(
            title=f"Edit experiment · {row.name}",
            name=row.name,
            description=row.raw.description,
            tags=row.raw.tags,
        )
        experiment_id = row.key
        self.app.push_screen(
            dialog,
            callback=lambda res: self._on_edit_submitted(experiment_id, res),
        )

    def _on_edit_submitted(
        self, experiment_id: str, result: EntityEditResult | None
    ) -> None:
        if result is None:
            return
        body = UpdateExperiment(
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
        self._run_update(experiment_id, body)

    @work(thread=True, group="experiments-update")
    def _run_update(self, experiment_id: str, body: UpdateExperiment) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.update_experiment(experiment_id, body)
        self.app.call_from_thread(self._on_update_result, result, experiment_id)

    def _on_update_result(
        self, result: Result[Any], experiment_id: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "update failed"
            self._lumlflow_app.show_toast(
                f"Edit failed: {msg}", severity="error"
            )
            return
        # The mutate returns a bare `Experiment` (no models). Find the
        # current row and merge the updated fields so other fields
        # (group_name, models, etc.) stay intact.
        updated = result.unwrap()
        for i, row in enumerate(self._rows):
            if row.key == experiment_id:
                merged = row.raw.model_copy(
                    update={
                        "name": updated.name,
                        "description": updated.description,
                        "tags": updated.tags,
                    }
                )
                self._rows[i] = self._to_row(merged)
                break
        try:
            table = self.query_one("#experiments-table", DataTable)
            new_row = next(r for r in self._rows if r.key == experiment_id)
            cells = self._render_row_cells(new_row)
            for col, cell in zip(table.ordered_columns, cells, strict=False):
                table.update_cell(experiment_id, col.key, cell)
        except Exception:
            self.load_first_page()
        self._lumlflow_app.show_toast(
            "Experiment updated.", severity="success", duration=2.0
        )

    def action_delete_focused(self) -> None:
        row = self._focused_row()
        if row is None:
            return
        dialog = ConfirmDialog(
            title="Delete experiment",
            message=(
                f"Delete experiment {row.name!r}? This action cannot "
                "be undone."
            ),
            confirm_label="Delete",
            destructive=True,
        )
        experiment_id = row.key
        self.app.push_screen(
            dialog,
            callback=lambda confirmed: self._on_delete_confirmed(
                experiment_id, confirmed
            ),
        )

    def _on_delete_confirmed(
        self, experiment_id: str, confirmed: bool | None
    ) -> None:
        if not confirmed:
            return
        self._run_delete(experiment_id)

    @work(thread=True, group="experiments-delete")
    def _run_delete(self, experiment_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.delete_experiment(experiment_id)
        self.app.call_from_thread(
            self._on_delete_result, result, experiment_id
        )

    def _on_delete_result(
        self, result: Result[Any], experiment_id: str
    ) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "delete failed"
            # 409 constraint failures (experiment has linked models) are
            # not fatal — surface as a warning toast per SPEC.
            if err and err.is_conflict:
                self._lumlflow_app.show_toast(
                    f"Delete blocked: {msg}", severity="warning"
                )
            else:
                self._lumlflow_app.show_toast(
                    f"Delete blocked: {msg}", severity="error"
                )
            return
        self._rows = [r for r in self._rows if r.key != experiment_id]
        try:
            table = self.query_one("#experiments-table", DataTable)
            table.remove_row(experiment_id)
        except Exception:
            self.load_first_page()
            return
        self._update_empty_state()
        self._lumlflow_app.show_toast(
            "Experiment deleted.", severity="success", duration=2.0
        )

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        # DataTable consumes Enter for its own `select_cursor` binding,
        # which prevents the screen-level `Binding("enter", "open_focused")`
        # from firing. Translate the bubbled `RowSelected` message into a
        # drill-in so Enter behaves identically to `→`.
        if event.data_table.id != "experiments-table":
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

    # ----- loading indicator -----

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        self._lumlflow_app.set_loading(loading)
        # Show an in-panel "Loading…" line only on the first page fetch,
        # while the table is still empty — once rows are visible the
        # header spinner is enough.
        try:
            indicator = self.query_one("#experiments-loading", Static)
        except Exception:
            return
        if loading and not self._rows:
            indicator.add_class("-visible")
        else:
            indicator.remove_class("-visible")

    # ----- live refresh -----

    def refresh_live(self) -> None:
        """Re-fetch the visible window and apply diffs in place.

        Status flips (`active` → `completed` / `error`), newly appeared
        experiments, and tag/duration updates are merged into the table
        without losing the user's cursor or scroll position. The
        refresh respects the active search/filter and sort.
        """

        if self._loading or self.facade is None:
            return
        visible = max(self._page_size, len(self._rows))
        self._refresh_visible_window(limit=visible)

    @work(thread=True, exclusive=True, group="experiments-refresh")
    def _refresh_visible_window(self, *, limit: int) -> None:
        facade = self.facade
        if facade is None:
            return
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        if self._all_experiments:
            group_ids = self._all_group_ids_cache
            if group_ids is None:
                groups_res = facade.list_groups(limit=1000)
                if not groups_res.ok:
                    return
                group_ids = [g.id for g in groups_res.unwrap().items]
                self._all_group_ids_cache = group_ids
            if not group_ids:
                return
            result = facade.list_groups_experiments(
                group_ids,
                limit=limit,
                cursor=None,
                sort_by=self._sort_by,
                order=order,
                search=self._combined_search(),
            )
        else:
            assert self._group_id is not None
            result = facade.list_group_experiments(
                self._group_id,
                limit=limit,
                cursor=None,
                sort_by=self._sort_by,
                order=order,
                search=self._combined_search(),
            )
        self.app.call_from_thread(self._on_refresh_result, result)

    def _on_refresh_result(self, result: Result[Any]) -> None:
        if not result.ok:
            return
        page = result.unwrap()
        new_rows = [self._to_row(e) for e in page.items]
        self._apply_diff(new_rows)

    def _apply_diff(self, new_rows: list[_ExperimentRow]) -> None:
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
            table = self.query_one("#experiments-table", DataTable)
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
        self._update_panel_subtitle()

    @staticmethod
    def _row_differs(a: _ExperimentRow, b: _ExperimentRow) -> bool:
        return (
            a.name != b.name
            or a.status != b.status
            or a.duration != b.duration
            or tuple(a.tags) != tuple(b.tags)
            or a.group_name != b.group_name
            or a.created_at != b.created_at
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
