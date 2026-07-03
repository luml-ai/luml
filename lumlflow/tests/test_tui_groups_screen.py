"""Pilot tests for the Groups home screen.

Covers SPEC.md task: "Build the groups home screen" — list with the
synthetic 'All experiments' entry, search, sort, lazy pagination,
edit/delete dialogs with constraint handling, and first-run empty
state.

All tests use Textual's headless `App.run_test()` + `Pilot` against
an in-memory seeded `ExperimentTracker` so the suite is deterministic
and fast — no network, no real filesystem store, no wall-clock waits.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.groups import (
    ALL_EXPERIMENTS_KEY,
    GroupsScreen,
)
from lumlflow.tui.widgets import PanelFrame
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
    SortChooserDialog,
    SortChooserResult,
)
from textual.widgets import DataTable, Input, Static


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade)


def _seed_groups(tracker: ExperimentTracker, count: int) -> list[str]:
    """Create `count` groups; return their names in insertion order."""

    names: list[str] = []
    for i in range(count):
        group = tracker.create_group(f"grp-{i:03d}", description=f"group {i}")
        names.append(group.name)
    return names


def _row_keys(table: DataTable) -> list[str]:
    return [row.key.value or "" for row in table.ordered_rows]


class TestEmptyState:
    async def test_empty_store_shows_first_run_state(
        self, facade: DataFacade, tmp_path: Path
    ) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            empty = screen.query_one("#groups-empty", Static)
            text = str(empty.render())
            assert "No groups yet" in text
            # The active store path is surfaced so users know where the
            # TUI is looking for runs.
            assert str(tmp_path / "experiments") in text
            # The table is hidden, the empty state is visible.
            table = screen.query_one("#groups-table", DataTable)
            assert table.display is False

    async def test_non_empty_store_hides_empty_state(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 3)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            # Give the worker a moment to populate the table.
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#groups-table", DataTable)
            assert table.display is True
            # Synthetic "All experiments" row appears first.
            assert table.row_count == 4  # 3 groups + synthetic All
            assert ALL_EXPERIMENTS_KEY in _row_keys(table)


class TestStoreUriWiring:
    """The CLI launches the app with a resolved `store_uri` and no
    pre-built facade; the app must read from exactly that store.
    """

    async def test_groups_load_from_store_uri_without_facade(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "experiments"
        seed_tracker = ExperimentTracker(f"sqlite://{store}")
        for name in ("alpha", "beta"):
            seed_tracker.create_group(name)

        app = LumlflowApp(
            store_uri=f"sqlite://{store}", show_first_run_hint=False
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            assert table.display is True
            # 2 seeded groups + synthetic "All experiments".
            assert table.row_count == 3
            assert ALL_EXPERIMENTS_KEY in _row_keys(table)

    async def test_empty_state_shows_store_uri_path(self, tmp_path: Path) -> None:
        store = tmp_path / "experiments"
        ExperimentTracker(f"sqlite://{store}")  # create the (empty) store

        app = LumlflowApp(
            store_uri=f"sqlite://{store}", show_first_run_hint=False
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            empty = screen.query_one("#groups-empty", Static)
            assert str(store) in str(empty.render())


class TestSyntheticAllExperimentsRow:
    async def test_present_on_first_page(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            keys = _row_keys(screen.query_one("#groups-table", DataTable))
            assert keys[0] == ALL_EXPERIMENTS_KEY

    async def test_hidden_when_search_active(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 3)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            search = app.screen.query_one("#groups-search", Input)
            search.value = "grp-001"
            # Trigger debounced apply directly to avoid the timer race.
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            screen._apply_search("grp-001")
            await pilot.pause()
            await pilot.pause()
            keys = _row_keys(screen.query_one("#groups-table", DataTable))
            assert ALL_EXPERIMENTS_KEY not in keys


class TestNavigation:
    async def test_keyboard_motion(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 3)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            assert table.cursor_row == 0
            await pilot.press("j")
            await pilot.pause()
            assert table.cursor_row == 1
            await pilot.press("j")
            await pilot.pause()
            assert table.cursor_row == 2
            await pilot.press("k")
            await pilot.pause()
            assert table.cursor_row == 1
            # `G` should jump to the last row. Real terminals deliver
            # Shift+G as the character key "G" (never "shift+g"), so the
            # binding and this press must both use the character form.
            await pilot.press("G")
            await pilot.pause()
            assert table.cursor_row == table.row_count - 1
            # `g` should jump back to the top.
            await pilot.press("g")
            await pilot.pause()
            assert table.cursor_row == 0

    async def test_enter_on_synthetic_row_drills_in_to_all_experiments(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from lumlflow.tui.screens.experiments import ExperimentsScreen

        _seed_groups(tracker, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # The cursor starts on the synthetic All row; Enter must
            # drill in identically to `→` (the SPEC's Enter-drill-in
            # contract — DataTable's built-in `select_cursor` binding
            # used to swallow Enter so only `→` worked).
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            assert app.screen._all_experiments is True


class TestSearch:
    async def test_search_filters_rows(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Two groups with distinct names; search for one of them.
        tracker.create_group("alpha")
        tracker.create_group("beta")
        tracker.create_group("gamma")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            search = screen.query_one("#groups-search", Input)
            assert app.focused is search
            # Trigger the search synchronously rather than typing through
            # the debounce — the debouncing is exercised separately.
            screen._apply_search("alpha")
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#groups-table", DataTable)
            keys = _row_keys(table)
            # Only the matching group remains, and the synthetic All row
            # is dropped when a filter is active.
            assert ALL_EXPERIMENTS_KEY not in keys
            assert all(k != ALL_EXPERIMENTS_KEY for k in keys)
            assert len(keys) == 1

    async def test_search_letters_are_literal(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Hard invariant: letters typed in search must NOT invoke commands."""

        tracker.create_group("alpha")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            search = app.screen.query_one("#groups-search", Input)
            # `d` should NOT trigger delete, `e` should NOT trigger edit,
            # `s` should NOT trigger sort — they're literal text.
            await pilot.press("d", "e", "s", "t")
            await pilot.pause()
            assert search.value == "dest"
            # No dialog popped — we're still on the Groups screen.
            assert isinstance(app.screen, GroupsScreen)

    async def test_search_escape_closes_and_restores(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        tracker.create_group("beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            await pilot.press("slash")
            await pilot.pause()
            screen._apply_search("alpha")
            await pilot.pause()
            await pilot.pause()
            # Filtered to one row.
            table = screen.query_one("#groups-table", DataTable)
            assert table.row_count == 1
            # Escape should clear the search and reload.
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert screen._search is None
            # Now we should see the synthetic row + both groups.
            assert table.row_count == 3


class TestSort:
    async def test_open_sort_dialog(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert isinstance(app.screen, SortChooserDialog)

    async def test_apply_sort_reloads(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = next(
                s for s in app.screen_stack if isinstance(s, GroupsScreen)
            )
            # Apply a sort change programmatically (the dialog is exercised
            # in its own test); confirm the screen state updates.
            screen._apply_sort_result(SortChooserResult(field="name", order="asc"))
            await pilot.pause()
            await pilot.pause()
            assert screen._sort_by == "name"
            assert screen._order == "asc"


class TestEdit:
    async def test_edit_dialog_opens_for_real_row(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("orig-name", description="orig desc")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Move past synthetic row to the first real group.
            await pilot.press("j")
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == group.id
            await pilot.press("e")
            await pilot.pause()
            assert isinstance(app.screen, EditEntityDialog)
            # Initial values pre-filled.
            name_input = app.screen.query_one("#edit-name", Input)
            assert name_input.value == "orig-name"

    async def test_edit_dialog_skipped_for_synthetic_row(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Cursor on synthetic row.
            assert table.cursor_row == 0
            await pilot.press("e")
            await pilot.pause()
            # No dialog should have opened — still on Groups screen.
            assert isinstance(app.screen, GroupsScreen)

    async def test_edit_updates_row_in_place(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("orig", description="d")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            # Drive the edit via the internal callback.
            screen._on_edit_submitted(
                group.id,
                EntityEditResult(name="renamed"),
            )
            await pilot.pause()
            await pilot.pause()
            # The row state in the screen should reflect the new name.
            renamed = next(r for r in screen._rows if r.key == group.id)
            assert renamed.name == "renamed"


class TestDelete:
    async def test_delete_empty_group(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("to-go")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            screen._on_delete_confirmed(group.id, True)
            await pilot.pause()
            await pilot.pause()
            assert all(r.key != group.id for r in screen._rows)

    async def test_delete_blocked_by_linked_experiments(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("with-exps")
        tracker.start_experiment(name="some-exp", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            screen._on_delete_confirmed(group.id, True)
            await pilot.pause()
            await pilot.pause()
            # Group still present (constraint failure).
            assert any(r.key == group.id for r in screen._rows)

    async def test_delete_synthetic_row_is_noop(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            assert table.cursor_row == 0
            await pilot.press("d")
            await pilot.pause()
            # No dialog appeared.
            assert isinstance(app.screen, GroupsScreen)

    async def test_delete_confirm_dialog_opens(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("doomed")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            table = app.screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Move to the real group.
            await pilot.press("j")
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == group.id
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)


class TestPagination:
    async def test_paginated_load(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Lazy pagination loads the next page when the cursor approaches the end."""

        # Use a tiny page size so two pages are required.
        _seed_groups(tracker, 8)

        async with LumlflowApp(facade=facade).run_test() as pilot:
            await pilot.pause()
            screen = pilot.app.screen
            assert isinstance(screen, GroupsScreen)
            # Reconfigure for tiny page size before any data fetch.
            screen._page_size = 3
            screen.load_first_page()
            await pilot.pause()
            await pilot.pause()
            # After first page: synthetic + 3 real = 4 rows.
            assert len(screen._rows) == 4
            assert screen._has_more is True
            # Triggering next page via the highlight handler should grow
            # the visible window.
            screen.load_next_page()
            await pilot.pause()
            await pilot.pause()
            assert len(screen._rows) >= 7


class TestPanelFrameReskin:
    """SPEC task: Reskin the groups screen as a framed panel."""

    async def test_groups_table_is_wrapped_in_panel(
        self, facade: DataFacade
    ) -> None:
        """The groups list must live inside a titled ``PanelFrame``."""

        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            panel = screen.query_one("#groups-panel", PanelFrame)
            table = screen.query_one("#groups-table", DataTable)
            # The table must be a descendant of the panel.
            current = table.parent
            while current is not None and current is not panel:
                current = current.parent
            assert current is panel

    async def test_panel_title_is_groups(self, facade: DataFacade) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            panel = screen.query_one("#groups-panel", PanelFrame)
            assert panel.title == "Groups"
            # The title is also pushed onto the rendered border.
            assert panel.border_title == "Groups"

    async def test_panel_subtitle_reflects_count_and_sort(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 3)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            panel = screen.query_one("#groups-panel", PanelFrame)
            subtitle = panel.subtitle
            # Count excludes the synthetic "All experiments" row so the
            # number matches what's actually in the store.
            assert "3 groups" in subtitle
            # Sort field is part of the subtitle so the chrome surfaces
            # what's driving the listing.
            assert "sort" in subtitle.lower()

    async def test_panel_subtitle_reflects_filter(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("alpha")
        tracker.create_group("beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            screen._apply_search("alpha")
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#groups-panel", PanelFrame)
            assert "alpha" in panel.subtitle

    async def test_empty_state_lives_inside_panel(
        self, facade: DataFacade
    ) -> None:
        """The first-run empty message renders centered in the panel."""

        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            panel = screen.query_one("#groups-panel", PanelFrame)
            empty = screen.query_one("#groups-empty", Static)
            # Empty state is a child of the panel so it inherits the
            # panel's surface styling and stays inside the border.
            current = empty.parent
            while current is not None and current is not panel:
                current = current.parent
            assert current is panel
            # The empty state is visible and the table is hidden when no
            # rows are loaded.
            assert "-hidden" not in empty.classes
            table = screen.query_one("#groups-table", DataTable)
            assert table.display is False

    async def test_populated_state_swaps_in_table(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_groups(tracker, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            empty = screen.query_one("#groups-empty", Static)
            table = screen.query_one("#groups-table", DataTable)
            # With rows loaded the empty state hides and the table shows.
            assert "-hidden" in empty.classes
            assert table.display is True


class TestHeaderClickSort:
    """Clicking a column header sorts by it; clicking again flips order."""

    async def test_header_click_sorts_and_toggles(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from types import SimpleNamespace

        from rich.text import Text

        for name in ("alpha", "beta"):
            tracker.create_group(name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, GroupsScreen)
            table = screen.query_one("#groups-table", DataTable)
            event = SimpleNamespace(data_table=table, label=Text("Name"))
            screen.on_data_table_header_selected(event)
            await pilot.pause()
            assert screen._sort_by == "name"
            assert screen._order == "asc"
            # Second click on the same column flips the order.
            screen.on_data_table_header_selected(event)
            await pilot.pause()
            assert screen._sort_by == "name"
            assert screen._order == "desc"
            # A non-sortable column is ignored.
            before = (screen._sort_by, screen._order)
            screen.on_data_table_header_selected(
                SimpleNamespace(data_table=table, label=Text("Tags"))
            )
            await pilot.pause()
            assert (screen._sort_by, screen._order) == before
