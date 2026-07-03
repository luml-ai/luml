"""Groups home screen — the entry point of the navigation stack.

Renders all experiment groups in a `DataTable`, prefixed with a
synthetic "All experiments" row that drills into a cross-group
experiments view. Implements the SPEC's interaction contract: `/` for
incremental search, `s` for the sort chooser, `e`/`d` for edit/delete,
`Enter` to drill in, lazy pagination as the user scrolls, plus a
welcoming first-run empty state when the store is fresh.

All data work runs on Textual workers via the `DataFacade`; the event
loop never blocks on SQLite. Search input is debounced so we don't
issue a query on every keystroke.
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
from lumlflow.schemas.experiment_groups import (
    Group,
    GroupsSortBy,
    UpdateGroup,
)
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.keymap import Scope
from lumlflow.tui.screens.base import BaseScreen
from lumlflow.tui.widgets import BreadcrumbSegment, PaletteEntry, PanelFrame
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
    SortChooserDialog,
    SortChooserResult,
)

if TYPE_CHECKING:
    from lumlflow.tui.app import LumlflowApp

# Synthetic row key for "All experiments" — chosen so it never collides
# with a real group id (groups use uuid-like strings).
ALL_EXPERIMENTS_KEY = "__all_experiments__"


def _render_tag_chips(tags: list[str]) -> Text:
    """Render a list of tags as colored chip-style text.

    Each chip is wrapped in thin spaces so the tag text reads as its own
    pill rather than blending with the next one. Color picking stays
    deterministic per tag string so the same tag always uses the same
    color across screens.
    """

    out = Text()
    for i, tag in enumerate(tags):
        if i > 0:
            out.append(" ")
        color_index = hash(tag) % 8
        out.append(f" {tag} ", style=f"bold $tag-{color_index} on $panel")
    return out

# Default page size for lazy pagination. Kept modest so even on giant
# stores the first page renders quickly; subsequent pages load as the
# user scrolls past the last visible row.
PAGE_SIZE = 50


_SORT_FIELDS: list[tuple[str, str]] = [
    (GroupsSortBy.NAME.value, "Name"),
    (GroupsSortBy.CREATED_AT.value, "Created"),
    (GroupsSortBy.LAST_MODIFIED.value, "Last modified"),
    (GroupsSortBy.DESCRIPTION.value, "Description"),
]

# Table column label → sortable field, for header-click sorting.
# Columns without a backing sort field (Tags) are simply not mapped.
_HEADER_SORT_FIELDS: dict[str, str] = {
    "Name": GroupsSortBy.NAME.value,
    "Description": GroupsSortBy.DESCRIPTION.value,
    "Created": GroupsSortBy.CREATED_AT.value,
}


@dataclass
class _GroupRow:
    """One row in the data table — either a real group or the synthetic All row."""

    key: str
    name: str
    description: str
    tags: list[str]
    created_at: str
    is_synthetic: bool = False
    raw: Group | None = None


class GroupsScreen(BaseScreen):
    """Groups list, sort, search, lazy pagination.

    The screen owns the active `sort_by`/`order`/`search` state and the
    pagination cursor; the facade is told what to fetch, returns a
    page, and we append rows to the table. Mutations re-render the
    affected row in place (edit) or remove it (delete).
    """

    DEFAULT_CSS = """
    GroupsScreen {
        layout: vertical;
    }
    GroupsScreen #groups-body {
        height: 1fr;
        layout: vertical;
        padding: 0 1;
    }
    GroupsScreen #groups-search {
        margin: 0 1 1 1;
        display: none;
    }
    GroupsScreen #groups-search.-visible {
        display: block;
    }
    GroupsScreen #groups-panel {
        height: 1fr;
    }
    GroupsScreen #groups-table {
        height: 1fr;
    }
    GroupsScreen #groups-empty {
        height: 1fr;
        padding: 2 4;
        content-align: center middle;
        text-align: center;
        color: $foreground 70%;
    }
    GroupsScreen #groups-empty.-hidden {
        display: none;
    }
    GroupsScreen #groups-loading {
        height: 1;
        padding: 0 1;
        color: $accent;
        display: none;
    }
    GroupsScreen #groups-loading.-visible {
        display: block;
    }
    """

    BINDINGS = [
        Binding("slash", "begin_search", "Search", show=False),
        Binding("s", "open_sort", "Sort", show=False),
        Binding("e", "edit_focused", "Edit", show=False),
        Binding("d", "delete_focused", "Delete", show=False),
        Binding("y", "yank_focused", "Yank id", show=False),
        Binding("enter", "open_focused", "Open", show=False),
        # vim-style navigation
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("g", "cursor_first", "First", show=False),
        Binding("shift+g", "cursor_last", "Last", show=False),
    ]

    AUTO_FOCUS = "#groups-table"

    breadcrumb_label = "Groups"

    # Debounce window for incremental search (in seconds).
    SEARCH_DEBOUNCE = 0.2

    def __init__(
        self,
        *,
        facade: DataFacade | None = None,
        page_size: int = PAGE_SIZE,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._facade = facade
        self._page_size = page_size
        self._sort_by: str = GroupsSortBy.CREATED_AT.value
        self._order: str = SortOrder.DESC.value
        self._search: str | None = None
        self._cursor: str | None = None
        self._has_more: bool = False
        self._loading: bool = False
        self._rows: list[_GroupRow] = []
        self._search_timer: Any = None

    # ----- composition -----

    def compose_content(self) -> Iterable:  # type: ignore[override]
        with Container(id="groups-body"):
            yield Input(
                placeholder="Search groups (Esc to close)",
                id="groups-search",
            )
            with PanelFrame(
                title=self._panel_title(),
                subtitle=self._panel_subtitle(),
                fill=True,
                id="groups-panel",
            ):
                yield Static("Loading…", id="groups-loading")
                yield Static(
                    self._empty_state_text(),
                    id="groups-empty",
                )
                yield DataTable(
                    id="groups-table", cursor_type="row", zebra_stripes=True
                )

    def on_mount(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.add_columns("Name", "Tags", "Description", "Created")
        # Empty state visible by default; load_first_page will hide if
        # rows arrive. Skip the initial fetch when no facade is wired
        # — that path is used by chrome-only tests.
        self._update_empty_state()
        self._update_panel_subtitle()
        if self.facade is not None:
            self.load_first_page()

    # ----- scope wiring -----

    def breadcrumb_segments(self) -> tuple[BreadcrumbSegment, ...]:
        return (BreadcrumbSegment("Groups"),)

    def footer_scopes(self) -> tuple[Scope, ...]:
        return ("global", "list", "actions")

    # ----- facade -----

    @property
    def facade(self) -> DataFacade | None:
        if self._facade is not None:
            return self._facade
        app = self.app
        # Only return the app's facade if one has already been
        # constructed — accessing the lazy `app.facade` property would
        # otherwise build a default `DataFacade()` (which touches the
        # default tracker / filesystem) during chrome-only tests.
        prebuilt = getattr(app, "_facade", None)
        return prebuilt

    @property
    def _lumlflow_app(self) -> LumlflowApp:
        """Typed accessor for the host app's screen helpers.

        Casting via this property keeps the call sites tidy and gives
        the type checker visibility into `show_toast`/`set_loading`.
        """

        return cast("LumlflowApp", self.app)

    # ----- data loading -----

    def load_first_page(self) -> None:
        """Reset pagination state and reload the first page."""

        self._cursor = None
        self._has_more = False
        self._rows = []
        try:
            table = self.query_one("#groups-table", DataTable)
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

    @work(thread=True, exclusive=True, group="groups")
    def _fetch_page(self, *, reset: bool) -> None:
        facade = self.facade
        if facade is None:
            self.app.call_from_thread(
                self._on_page_failure, "facade unavailable", reset
            )
            return
        try:
            sort_by = GroupsSortBy(self._sort_by)
        except ValueError:
            sort_by = GroupsSortBy.CREATED_AT
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        result = facade.list_groups(
            limit=self._page_size,
            cursor=None if reset else self._cursor,
            sort_by=sort_by,
            order=order,
            search=self._search,
        )
        self.app.call_from_thread(self._on_page_result, result, reset)

    def _on_page_result(self, result: Result[Any], reset: bool) -> None:
        self._set_loading(False)
        if not result.ok:
            message = result.error.message if result.error else "error"
            self._on_page_failure(message, reset)
            return
        page = result.unwrap()
        new_rows: list[_GroupRow] = []
        # Inject synthetic "All experiments" row at the top of an
        # unfiltered listing — but only when there are real groups, so
        # a fresh store shows the welcoming first-run empty state and
        # not a single confusing synthetic row.
        if reset and not self._search and page.items:
            new_rows.append(self._all_experiments_row())
        new_rows.extend(self._to_row(g) for g in page.items)
        self._rows = self._rows + new_rows if not reset else new_rows
        self._cursor = page.cursor
        self._has_more = page.cursor is not None and len(page.items) >= self._page_size
        self._refresh_table_after_page(new_rows, reset=reset)

    def _on_page_failure(self, message: str, _reset: bool) -> None:
        self._set_loading(False)
        self._lumlflow_app.show_toast(
            f"Could not load groups: {message}", severity="error"
        )

    def _refresh_table_after_page(
        self, new_rows: list[_GroupRow], *, reset: bool
    ) -> None:
        table = self.query_one("#groups-table", DataTable)
        if reset:
            table.clear()
        for row in new_rows:
            table.add_row(*self._render_row_cells(row), key=row.key)
        self._update_empty_state()
        self._update_panel_subtitle()

    def _update_empty_state(self) -> None:
        empty = self.query_one("#groups-empty", Static)
        table = self.query_one("#groups-table", DataTable)
        if not self._rows:
            empty.update(self._empty_state_text())
            empty.remove_class("-hidden")
            table.display = False
        else:
            empty.add_class("-hidden")
            table.display = True
        self._update_panel_subtitle()

    def _empty_state_text(self) -> str:
        if self._search:
            return (
                f"No groups match {self._search!r}.\n\n"
                "Press [Esc] to clear the search."
            )
        # First-run / fresh-install welcome.
        return (
            "Welcome to Lumlflow.\n\n"
            "No experiment groups yet — they appear here as your training "
            "scripts log to this store.\n\n"
            f"Store: {self._store_path()}\n\n"
            "Press [?] for help · [:] for commands"
        )

    def _store_path(self) -> str:
        """Resolved filesystem path of the store the TUI is reading.

        Derived from the live tracker so a custom store (e.g. one passed
        on the CLI) is reflected accurately; falls back to the configured
        default when no facade has been built yet.
        """
        facade = self.facade
        backend = getattr(getattr(facade, "tracker", None), "backend", None)
        base_path = getattr(backend, "base_path", None)
        if base_path is not None:
            return str(base_path)
        from lumlflow.settings import get_config

        return get_config().BACKEND_STORE_URI

    # ----- row rendering -----

    def _all_experiments_row(self) -> _GroupRow:
        return _GroupRow(
            key=ALL_EXPERIMENTS_KEY,
            name="All experiments",
            description="Browse experiments across every group",
            tags=[],
            created_at="—",
            is_synthetic=True,
        )

    def _to_row(self, group: Group) -> _GroupRow:
        return _GroupRow(
            key=group.id,
            name=group.name,
            description=group.description or "",
            tags=group.tags or [],
            created_at=group.created_at.strftime("%Y-%m-%d %H:%M")
            if group.created_at is not None
            else "",
            raw=group,
        )

    def _render_row_cells(self, row: _GroupRow) -> tuple[Text, Text, Text, Text]:
        name = Text(row.name)
        if row.is_synthetic:
            name.stylize("bold $accent")
        tags = _render_tag_chips(row.tags)
        description = Text(row.description, overflow="ellipsis")
        if row.is_synthetic:
            description.stylize("italic")
        created = Text(row.created_at, style="dim")
        return name, tags, description, created

    # ----- selection / drill-in -----

    def _focused_row(self) -> _GroupRow | None:
        table = self.query_one("#groups-table", DataTable)
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
        from lumlflow.tui.screens.experiments import ExperimentsScreen

        # Pass the resolved facade so the child screen sees the same
        # instance — `self._facade` can be None when the GroupsScreen
        # was constructed with no explicit facade and pulled it from
        # the app instead.
        facade = self.facade
        if row.is_synthetic:
            screen = ExperimentsScreen(
                facade=facade,
                all_experiments=True,
            )
        else:
            screen = ExperimentsScreen(
                facade=facade,
                group_id=row.key,
                group_name=row.name,
            )
        # Cursor/scroll survive the round-trip because the screen stays
        # alive in Textual's stack while the child is on top.
        self._lumlflow_app.push_screen(screen)

    def action_cursor_down(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        table.action_cursor_up()

    def action_cursor_first(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        if table.row_count == 0:
            return
        table.move_cursor(row=0)

    def action_cursor_last(self) -> None:
        table = self.query_one("#groups-table", DataTable)
        if table.row_count == 0:
            return
        table.move_cursor(row=table.row_count - 1)

    def action_yank_focused(self) -> None:
        row = self._focused_row()
        if row is None or row.is_synthetic:
            return
        self._lumlflow_app.yank_to_clipboard(row.key, label="group id")

    # ----- palette jump-to -----

    def palette_entries(self) -> list[PaletteEntry]:
        """Contribute jump-to entries for every currently-loaded group.

        The palette ("Type to search · jump to · run action") merges
        these into its fuzzy index so the user can type a group name
        and Enter to drill straight in. Only the loaded rows are
        surfaced — lazy pagination owns the rest, consistent with
        the SPEC's viewport-bounded data rule.
        """

        entries: list[PaletteEntry] = []
        for row in self._rows:
            if row.is_synthetic:
                entries.append(
                    PaletteEntry(
                        label=row.name,
                        description="Browse experiments across every group",
                        kind="screen",
                        invoke=self._make_jump_invoke(row.key),
                        extra_search="all experiments",
                    )
                )
                continue
            entries.append(
                PaletteEntry(
                    label=row.name,
                    description=row.description or "Open group",
                    kind="group",
                    invoke=self._make_jump_invoke(row.key),
                    extra_search=" ".join(row.tags),
                )
            )
        return entries

    def _make_jump_invoke(self, row_key: str):
        """Build a no-arg callback that drills into the given row.

        The palette dismisses itself before invoking, so by the time
        this runs the GroupsScreen is the focused screen again.
        """

        def _invoke() -> None:
            for i, row in enumerate(self._rows):
                if row.key == row_key:
                    try:
                        table = self.query_one("#groups-table", DataTable)
                        table.move_cursor(row=i, animate=False)
                    except Exception:
                        pass
                    self.action_open_focused()
                    return

        return _invoke

    # ----- search -----

    def action_begin_search(self) -> None:
        search = self.query_one("#groups-search", Input)
        search.add_class("-visible")
        # Pre-fill with current search so the user can edit it.
        search.value = self._search or ""
        search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "groups-search":
            return
        if self._search_timer is not None:
            self._search_timer.stop()
        self._search_timer = self.set_timer(
            self.SEARCH_DEBOUNCE, lambda: self._apply_search(event.value)
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "groups-search":
            return
        # Enter on the search input commits and returns focus to the table.
        if self._search_timer is not None:
            self._search_timer.stop()
        self._apply_search(event.value)
        try:
            self.query_one("#groups-table", DataTable).focus()
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
            search = self.query_one("#groups-search", Input)
        except Exception:
            return False
        if "-visible" not in search.classes:
            return False
        search.remove_class("-visible")
        # Clear the active search and reload only if there was one.
        had_search = self._search is not None
        search.value = ""
        self._search = None
        try:
            self.query_one("#groups-table", DataTable).focus()
        except Exception:
            pass
        if had_search:
            self.load_first_page()
        return True

    def on_key(self, event) -> None:
        # Intercept Esc inside the search input to close it without
        # quitting the screen.
        if event.key != "escape":
            return
        focused = self.focused
        if focused is None:
            return
        if not isinstance(focused, Input) or focused.id != "groups-search":
            return
        if self._close_search_if_open():
            event.stop()

    # ----- sort -----

    def action_open_sort(self) -> None:
        dialog = SortChooserDialog(
            title="Sort groups",
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
        """Clicking a column header sorts by it (click again to flip).

        Mouse counterpart of the `s` sort dialog — both route through
        `_apply_sort_result` so state, subtitle, and refetch stay in
        one place.
        """

        if event.data_table.id != "groups-table":
            return
        field = _HEADER_SORT_FIELDS.get(str(event.label))
        if field is None:
            return
        if field == self._sort_by:
            order = "asc" if self._order == "desc" else "desc"
        else:
            order = "asc" if field == GroupsSortBy.NAME.value else "desc"
        self._apply_sort_result(SortChooserResult(field=field, order=order))

    def _format_sort_status(self) -> str:
        label_by_id = {fid: label for fid, label in _SORT_FIELDS}
        field_label = label_by_id.get(self._sort_by, self._sort_by)
        arrow = "↓" if self._order == "desc" else "↑"
        search_part = (
            f" · filter {self._search!r}" if self._search is not None else ""
        )
        return f"sort: {field_label} {arrow}{search_part}"

    def _panel_title(self) -> str:
        return "Groups"

    def _panel_subtitle(self) -> str:
        """Right-aligned subtitle: row count + active sort + filter."""

        # Exclude the synthetic "All experiments" row from the count so
        # the subtitle reflects how many real groups are loaded.
        real_count = sum(1 for r in self._rows if not r.is_synthetic)
        count_part = f"{real_count} group{'s' if real_count != 1 else ''}"
        return f"{count_part} · {self._format_sort_status()}"

    def _update_panel_subtitle(self) -> None:
        try:
            panel = self.query_one("#groups-panel", PanelFrame)
            panel.set_subtitle(self._panel_subtitle())
        except Exception:
            pass

    # ----- edit / delete -----

    def action_edit_focused(self) -> None:
        row = self._focused_row()
        if row is None or row.is_synthetic or row.raw is None:
            return
        dialog = EditEntityDialog(
            title=f"Edit group · {row.name}",
            name=row.name,
            description=row.raw.description,
            tags=row.raw.tags,
        )
        group_id = row.key
        self.app.push_screen(
            dialog,
            callback=lambda res: self._on_edit_submitted(group_id, res),
        )

    def _on_edit_submitted(
        self, group_id: str, result: EntityEditResult | None
    ) -> None:
        if result is None:
            return
        body = UpdateGroup(
            name=result.name,
            description=result.description,
            tags=result.tags,
        )
        # Only call the facade if at least one field was actually changed.
        if (
            body.name is None
            and body.description is None
            and body.tags is None
        ):
            return
        self._run_update(group_id, body)

    @work(thread=True, group="groups-update")
    def _run_update(self, group_id: str, body: UpdateGroup) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.update_group(group_id, body)
        self.app.call_from_thread(self._on_update_result, result, group_id)

    def _on_update_result(self, result: Result[Any], group_id: str) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "update failed"
            self._lumlflow_app.show_toast(
                f"Edit failed: {msg}", severity="error"
            )
            return
        # Replace the row in-place rather than reloading the whole page.
        updated_group: Group = result.unwrap()
        new_row = self._to_row(updated_group)
        for i, row in enumerate(self._rows):
            if row.key == group_id:
                self._rows[i] = new_row
                break
        try:
            table = self.query_one("#groups-table", DataTable)
            cells = self._render_row_cells(new_row)
            # `update_cell` requires a column key; use ordered_columns.
            for col, cell in zip(table.ordered_columns, cells, strict=False):
                table.update_cell(group_id, col.key, cell)
        except Exception:
            # If in-place update fails for any reason, reload the page.
            self.load_first_page()
        self._lumlflow_app.show_toast(
            "Group updated.", severity="success", duration=2.0
        )

    def action_delete_focused(self) -> None:
        row = self._focused_row()
        if row is None or row.is_synthetic:
            return
        dialog = ConfirmDialog(
            title="Delete group",
            message=(
                f"Delete group {row.name!r}? This action cannot be undone."
            ),
            confirm_label="Delete",
            destructive=True,
        )
        group_id = row.key
        self.app.push_screen(
            dialog,
            callback=lambda confirmed: self._on_delete_confirmed(
                group_id, confirmed
            ),
        )

    def _on_delete_confirmed(self, group_id: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        self._run_delete(group_id)

    @work(thread=True, group="groups-delete")
    def _run_delete(self, group_id: str) -> None:
        facade = self.facade
        if facade is None:
            return
        result = facade.delete_group(group_id)
        self.app.call_from_thread(self._on_delete_result, result, group_id)

    def _on_delete_result(self, result: Result[Any], group_id: str) -> None:
        if not result.ok:
            err = result.error
            msg = err.message if err else "delete failed"
            # 409 constraint failures (group has linked experiments) are
            # not fatal — surface as a clear info-level toast per SPEC.
            if err and err.is_conflict:
                self._lumlflow_app.show_toast(
                    f"Delete blocked: {msg}", severity="warning"
                )
            else:
                self._lumlflow_app.show_toast(
                    f"Delete blocked: {msg}", severity="error"
                )
            return
        # Remove the row in-place.
        self._rows = [r for r in self._rows if r.key != group_id]
        try:
            table = self.query_one("#groups-table", DataTable)
            table.remove_row(group_id)
        except Exception:
            self.load_first_page()
            return
        self._update_empty_state()
        self._lumlflow_app.show_toast(
            "Group deleted.", severity="success", duration=2.0
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # `DataTable` consumes Enter via its built-in `select_cursor`
        # binding, so the screen's `Binding("enter", "open_focused")`
        # never fires while the table is focused. Routing through the
        # `RowSelected` event makes Enter behave as "open / drill in"
        # uniformly, matching the `→` alias.
        if event.data_table.id != "groups-table":
            return
        self.action_open_focused()

    # ----- lazy pagination -----

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Load the next page when the cursor reaches the last few rows.
        # Guard against the trivial case where the list is smaller than
        # the prefetch threshold — without this, the initial highlight
        # at row 0 would trigger a chain of page fetches.
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
        # Show an in-panel "Loading…" line only on the very first page
        # fetch, when there are no rows yet — once the table has content
        # the header spinner is enough and an in-panel line would only
        # add noise on every pagination tick.
        try:
            indicator = self.query_one("#groups-loading", Static)
        except Exception:
            return
        if loading and not self._rows:
            indicator.add_class("-visible")
        else:
            indicator.remove_class("-visible")

    # ----- live refresh -----

    def refresh_live(self) -> None:
        """Re-fetch the visible window and apply diffs in place.

        Implements the `LiveRefreshable` protocol used by the app's
        `LiveRefreshScheduler`. Only the rows currently loaded into the
        table are re-fetched — we do not widen the working set as the
        store grows. The cursor and scroll position are preserved by
        manipulating individual cells rather than rebuilding the table.
        New rows are appended (subject to the visible-window cap) and
        rows that vanished are removed.
        """

        if self._loading or self.facade is None:
            return
        # Use the size of the currently visible window so we do not load
        # extra pages on refresh. If the user has scrolled to load more
        # pages, the visible window naturally grows over time.
        # Account for the synthetic "All experiments" row when present.
        visible = max(self._page_size, len(self._rows))
        self._refresh_visible_window(limit=visible)

    @work(thread=True, exclusive=True, group="groups-refresh")
    def _refresh_visible_window(self, *, limit: int) -> None:
        facade = self.facade
        if facade is None:
            return
        try:
            sort_by = GroupsSortBy(self._sort_by)
        except ValueError:
            sort_by = GroupsSortBy.CREATED_AT
        try:
            order = SortOrder(self._order)
        except ValueError:
            order = SortOrder.DESC
        result = facade.list_groups(
            limit=limit,
            cursor=None,
            sort_by=sort_by,
            order=order,
            search=self._search,
        )
        self.app.call_from_thread(self._on_refresh_result, result)

    def _on_refresh_result(self, result: Result[Any]) -> None:
        if not result.ok:
            return
        page = result.unwrap()
        new_rows: list[_GroupRow] = []
        if not self._search and page.items:
            new_rows.append(self._all_experiments_row())
        new_rows.extend(self._to_row(g) for g in page.items)
        self._apply_diff(new_rows)

    def _apply_diff(self, new_rows: list[_GroupRow]) -> None:
        """Apply a row-level diff to the table, pulsing what changed."""

        old_by_key = {r.key: r for r in self._rows}
        new_by_key = {r.key: r for r in new_rows}
        # Detect removals.
        removed = [k for k in old_by_key if k not in new_by_key]
        # Detect adds / updates.
        added: list[str] = []
        updated: list[str] = []
        for row in new_rows:
            if row.key not in old_by_key:
                added.append(row.key)
            elif self._row_differs(old_by_key[row.key], row):
                updated.append(row.key)
        if not (removed or added or updated):
            return
        # Save the cursor before mutating the table so we can restore.
        try:
            table = self.query_one("#groups-table", DataTable)
            saved_cursor = table.cursor_row
        except Exception:
            table = None
            saved_cursor = 0
        self._rows = new_rows
        if table is not None:
            self._rebuild_table_rows(table, new_rows)
            # Restore cursor: clamp to the new row count.
            if table.row_count > 0:
                clamped = max(0, min(saved_cursor, table.row_count - 1))
                table.move_cursor(row=clamped, animate=False)
            self._pulse_changed_rows(table, added + updated)
        self._update_empty_state()
        self._update_panel_subtitle()

    @staticmethod
    def _row_differs(a: _GroupRow, b: _GroupRow) -> bool:
        return (
            a.name != b.name
            or a.description != b.description
            or tuple(a.tags) != tuple(b.tags)
            or a.created_at != b.created_at
        )

    def _rebuild_table_rows(
        self, table: DataTable, rows: list[_GroupRow]
    ) -> None:
        table.clear()
        for row in rows:
            table.add_row(*self._render_row_cells(row), key=row.key)

    def _pulse_changed_rows(
        self, table: DataTable, changed_keys: list[str]
    ) -> None:
        """Briefly mark changed rows so the user notices them.

        Implementation is minimal: the row's first cell is re-rendered
        with a `reverse` style for ~0.4s. Anything more elaborate would
        need a per-row animation; this keeps the refresh cycle cheap.
        """

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
