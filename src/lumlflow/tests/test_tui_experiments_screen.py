"""Pilot tests for the experiments list screen.

Covers SPEC.md task: "Build the experiments list screen" — experiments
table with status color coding and param/metric columns, sort, lazy
pagination, drill-in, quick search + advanced filter editor with live
validation, edit and delete (with constraint handling).

All tests use Textual's headless `App.run_test()` + `Pilot` against an
in-memory seeded `ExperimentTracker` so the suite is deterministic and
fast — no network, no real filesystem store, no wall-clock waits.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.schemas.experiments import ExperimentStatus
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.experiments import (
    ExperimentsScreen,
    _format_duration,
)
from lumlflow.tui.screens.groups import GroupsScreen
from lumlflow.tui.widgets import PanelFrame
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
    FilterEditorDialog,
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


def _seed_experiments(
    tracker: ExperimentTracker, group_name: str, count: int
) -> list[str]:
    """Create `count` experiments under `group_name`; return their ids."""

    ids: list[str] = []
    for i in range(count):
        exp_id = tracker.start_experiment(
            name=f"exp-{i:03d}", group=group_name
        )
        ids.append(exp_id)
    return ids


def _row_keys(table: DataTable) -> list[str]:
    return [row.key.value or "" for row in table.ordered_rows]


def _push_experiments_screen(
    app: LumlflowApp,
    facade: DataFacade,
    *,
    group_id: str | None = None,
    group_name: str | None = None,
    all_experiments: bool = False,
    page_size: int = 50,
) -> ExperimentsScreen:
    screen = ExperimentsScreen(
        facade=facade,
        group_id=group_id,
        group_name=group_name,
        all_experiments=all_experiments,
        page_size=page_size,
    )
    app.push_screen(screen)
    return screen


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_requires_group_or_all(self) -> None:
        with pytest.raises(ValueError):
            ExperimentsScreen()


# ---------------------------------------------------------------------------
# Drill-in from the groups screen
# ---------------------------------------------------------------------------


class TestDrillIn:
    async def test_open_group_pushes_experiments_screen(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("grp-a")
        _seed_experiments(tracker, group.name, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            groups_screen = app.screen
            assert isinstance(groups_screen, GroupsScreen)
            table = groups_screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Move past the synthetic All row to the real group, then
            # trigger the action directly — DataTable consumes the raw
            # `enter` key event in headless tests, so we call the
            # screen's open action explicitly.
            await pilot.press("j")
            await pilot.pause()
            groups_screen.action_open_focused()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            assert app.screen._group_id == group.id

    async def test_open_all_experiments(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("grp-all")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.pause()
            groups_screen = app.screen
            assert isinstance(groups_screen, GroupsScreen)
            table = groups_screen.query_one("#groups-table", DataTable)
            table.focus()
            await pilot.pause()
            # Cursor starts on the synthetic All row.
            groups_screen.action_open_focused()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)
            assert app.screen._all_experiments is True


# ---------------------------------------------------------------------------
# Listing & status color coding
# ---------------------------------------------------------------------------


class TestListing:
    async def test_renders_experiments_for_group(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        ids = _seed_experiments(tracker, group.name, 3)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            assert table.row_count == 3
            assert set(_row_keys(table)) == set(ids)

    async def test_empty_state_shown_when_no_experiments(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("empty")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            empty = screen.query_one("#experiments-empty", Static)
            assert "no experiments" in str(empty.render()).lower()

    async def test_active_status_uses_emphasized_style(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="active-one", group=group.name)
        # Created experiments are active until they're stopped/completed.
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            row = next(r for r in screen._rows if r.key == exp_id)
            assert row.status == ExperimentStatus.ACTIVE
            cells = screen._render_row_cells(row)
            # cells[0] is the selection marker column; name/status are at 1/2.
            name_cell = cells[1]
            status_cell = cells[2]
            # Both the name and status cells of an active experiment are
            # rendered bold with the active-status color variable.
            assert "bold" in str(name_cell.style)
            assert "status-active" in str(name_cell.style)
            assert "bold" in str(status_cell.style)
            assert "status-active" in str(status_cell.style)


class TestAllExperimentsMode:
    async def test_aggregates_across_groups(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        g1 = tracker.create_group("g1")
        g2 = tracker.create_group("g2")
        ids1 = _seed_experiments(tracker, g1.name, 2)
        ids2 = _seed_experiments(tracker, g2.name, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, all_experiments=True
            )
            await pilot.pause()
            await pilot.pause()
            keys = {r.key for r in screen._rows}
            assert set(ids1 + ids2).issubset(keys)


# ---------------------------------------------------------------------------
# Search (incremental)
# ---------------------------------------------------------------------------


class TestSearch:
    async def test_search_filters_rows(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        tracker.start_experiment(name="alpha", group=group.name)
        tracker.start_experiment(name="beta", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            screen._apply_search("alpha")
            await pilot.pause()
            await pilot.pause()
            assert len(screen._rows) == 1
            assert screen._rows[0].name == "alpha"

    async def test_search_letters_are_literal(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Modeless input invariant: letters in search input are literal."""

        group = tracker.create_group("g")
        tracker.start_experiment(name="x", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            search = screen.query_one("#experiments-search", Input)
            # `d` should NOT trigger delete; `e` should NOT trigger edit.
            await pilot.press("d", "e", "s", "t")
            await pilot.pause()
            assert search.value == "dest"
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_search_escape_closes_and_restores(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        tracker.start_experiment(name="alpha", group=group.name)
        tracker.start_experiment(name="beta", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            screen._apply_search("alpha")
            await pilot.pause()
            await pilot.pause()
            assert len(screen._rows) == 1
            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()
            assert screen._search is None
            assert len(screen._rows) == 2


# ---------------------------------------------------------------------------
# Advanced filter editor with live validation
# ---------------------------------------------------------------------------


class TestFilterEditor:
    async def test_open_filter_dialog(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            assert isinstance(app.screen, FilterEditorDialog)

    async def test_invalid_filter_shows_inline_error(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            dialog = app.screen
            assert isinstance(dialog, FilterEditorDialog)
            filter_input = dialog.query_one("#filter-input", Input)
            # Type something obviously invalid; the live validator should
            # surface an inline error.
            filter_input.value = "this is = not valid DSL >>"
            # Manually trigger validation so we don't depend on the
            # textual reactive plumbing in headless tests.
            dialog._run_validation(filter_input.value)
            await pilot.pause()
            validation = dialog.query_one("#filter-validation", Static)
            assert not dialog._last_validation.valid
            assert "✗" in str(validation.render())

    async def test_valid_filter_marked_ok(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            dialog = app.screen
            assert isinstance(dialog, FilterEditorDialog)
            filter_input = dialog.query_one("#filter-input", Input)
            filter_input.value = 'status = "active"'
            dialog._run_validation(filter_input.value)
            await pilot.pause()
            assert dialog._last_validation.valid

    async def test_invalid_filter_blocks_apply(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("f")
            await pilot.pause()
            dialog = app.screen
            assert isinstance(dialog, FilterEditorDialog)
            filter_input = dialog.query_one("#filter-input", Input)
            filter_input.value = "not valid >>"
            dialog._run_validation(filter_input.value)
            dialog.action_confirm()
            await pilot.pause()
            # The dialog should still be open — invalid filter blocks apply.
            assert isinstance(app.screen, FilterEditorDialog)
            # And the screen's filter is unchanged.
            assert screen._filter is None

    async def test_apply_filter_updates_screen(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        tracker.start_experiment(name="run-a", group=group.name)
        tracker.start_experiment(name="run-b", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            # Apply a valid filter directly via the screen callback.
            screen._apply_filter_result('name LIKE "%run-a%"')
            await pilot.pause()
            await pilot.pause()
            assert screen._filter == 'name LIKE "%run-a%"'
            assert len(screen._rows) == 1
            assert screen._rows[0].name == "run-a"


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


class TestSort:
    async def test_open_sort_dialog(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            assert isinstance(app.screen, SortChooserDialog)

    async def test_apply_sort_reloads(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            screen._apply_sort_result(
                SortChooserResult(field="name", order="asc")
            )
            await pilot.pause()
            await pilot.pause()
            assert screen._sort_by == "name"
            assert screen._order == "asc"

    async def test_invalid_sort_field_surfaces_400(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """A sort field rejected by the handler shows a non-fatal toast."""

        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            # Force an unsupported sort_by; the handler returns a 400.
            screen._sort_by = "nonexistent_field"
            screen.load_first_page()
            await pilot.pause()
            await pilot.pause()
            # The screen stays usable; rows are reset.
            assert isinstance(app.screen, ExperimentsScreen)
            assert screen._rows == []


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


class TestEdit:
    async def test_edit_dialog_opens(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="orig", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            await pilot.pause()
            # Cursor is at row 0 — the only experiment.
            assert _row_keys(table)[table.cursor_row] == exp_id
            await pilot.press("e")
            await pilot.pause()
            assert isinstance(app.screen, EditEntityDialog)
            name_input = app.screen.query_one("#edit-name", Input)
            assert name_input.value == "orig"

    async def test_edit_updates_row_in_place(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="orig", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            screen._on_edit_submitted(
                exp_id, EntityEditResult(name="renamed")
            )
            await pilot.pause()
            await pilot.pause()
            renamed = next(r for r in screen._rows if r.key == exp_id)
            assert renamed.name == "renamed"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_delete_experiment(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="to-del", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            screen._on_delete_confirmed(exp_id, True)
            await pilot.pause()
            await pilot.pause()
            assert all(r.key != exp_id for r in screen._rows)

    async def test_delete_blocked_by_linked_model(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(
            name="exp-with-model", group=group.name
        )
        # The deletion constraint applies when an experiment has a linked
        # model. We seed one via the SDK backend (a fake .luml blob is
        # enough — the handler only checks linkage, not model contents).
        model_file = tmp_path / "model.luml"
        model_file.write_bytes(b"fake-model-data")
        tracker.backend.log_model(exp_id, str(model_file), name="m1")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            screen._on_delete_confirmed(exp_id, True)
            await pilot.pause()
            await pilot.pause()
            # 409 constraint failure — experiment remains visible in the
            # screen's rows and the screen stays usable.
            assert any(r.key == exp_id for r in screen._rows)
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_delete_confirm_dialog_opens(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="doomed", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == exp_id
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    async def test_paginated_load(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 8)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Use a tiny page size so multiple pages are required.
            screen = _push_experiments_screen(
                app,
                facade,
                group_id=group.id,
                group_name=group.name,
                page_size=3,
            )
            await pilot.pause()
            await pilot.pause()
            assert len(screen._rows) == 3
            assert screen._has_more is True
            screen.load_next_page()
            await pilot.pause()
            await pilot.pause()
            assert len(screen._rows) >= 6


# ---------------------------------------------------------------------------
# Drill-in / yank
# ---------------------------------------------------------------------------


class TestActions:
    async def test_enter_drills_into_experiment_detail(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from lumlflow.tui.screens.experiment_detail import (
            ExperimentDetailScreen,
        )

        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 1)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            await pilot.pause()
            # Enter must drill in identically to `→` — DataTable's own
            # `select_cursor` binding used to swallow Enter, leaving only
            # the `→` alias working.
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ExperimentDetailScreen)

    async def test_yank_surfaces_id(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        exp_id = tracker.start_experiment(name="x", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            await pilot.pause()
            assert _row_keys(table)[table.cursor_row] == exp_id
            # Should not raise.
            screen.action_yank_focused()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)


# ---------------------------------------------------------------------------
# Breadcrumb segments
# ---------------------------------------------------------------------------


class TestBreadcrumb:
    async def test_single_group_breadcrumb(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("alpha-grp")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            segs = screen.breadcrumb_segments()
            assert tuple(s.label for s in segs) == ("Groups", "alpha-grp")

    async def test_all_experiments_breadcrumb(
        self, facade: DataFacade
    ) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, all_experiments=True
            )
            await pilot.pause()
            segs = screen.breadcrumb_segments()
            assert tuple(s.label for s in segs) == (
                "Groups",
                "All experiments",
            )


# ---------------------------------------------------------------------------
# _format_duration helper (pure function)
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_none(self) -> None:
        assert _format_duration(None) == "—"

    def test_sub_second(self) -> None:
        assert "ms" in _format_duration(0.123)

    def test_seconds(self) -> None:
        assert "s" in _format_duration(12.5)

    def test_minutes(self) -> None:
        assert "m" in _format_duration(125.0)

    def test_hours(self) -> None:
        assert "h" in _format_duration(7200.0)


# ---------------------------------------------------------------------------
# PanelFrame reskin: titled/subtitled panel wrapping the table.
# ---------------------------------------------------------------------------


class TestPanelFrameReskin:
    """SPEC task: Reskin the experiments screen as a framed panel."""

    async def test_experiments_table_is_wrapped_in_panel(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#experiments-panel", PanelFrame)
            table = screen.query_one("#experiments-table", DataTable)
            current = table.parent
            while current is not None and current is not panel:
                current = current.parent
            assert current is panel

    async def test_panel_title_includes_group_name(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("alpha-grp")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#experiments-panel", PanelFrame)
            assert "alpha-grp" in panel.title
            assert panel.border_title == panel.title

    async def test_all_experiments_panel_title(self, facade: DataFacade) -> None:
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, all_experiments=True
            )
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#experiments-panel", PanelFrame)
            assert panel.title == "All experiments"

    async def test_panel_subtitle_reflects_count_and_sort(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#experiments-panel", PanelFrame)
            subtitle = panel.subtitle
            assert "2 experiments" in subtitle
            assert "sort" in subtitle.lower()

    async def test_panel_subtitle_reflects_filter(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        tracker.start_experiment(name="run-a", group=group.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            screen._apply_filter_result('name LIKE "%run-a%"')
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#experiments-panel", PanelFrame)
            assert "filter" in panel.subtitle

    async def test_empty_state_lives_inside_panel(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("empty")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#experiments-panel", PanelFrame)
            empty = screen.query_one("#experiments-empty", Static)
            current = empty.parent
            while current is not None and current is not panel:
                current = current.parent
            assert current is panel
            assert "-hidden" not in empty.classes
            table = screen.query_one("#experiments-table", DataTable)
            assert table.display is False

    async def test_populated_state_swaps_in_table(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        group = tracker.create_group("g")
        _seed_experiments(tracker, group.name, 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, group_id=group.id, group_name=group.name
            )
            await pilot.pause()
            await pilot.pause()
            empty = screen.query_one("#experiments-empty", Static)
            table = screen.query_one("#experiments-table", DataTable)
            assert "-hidden" in empty.classes
            assert table.display is True


class TestHeaderClickSort:
    async def test_header_click_sorts_and_toggles(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from types import SimpleNamespace

        from rich.text import Text

        tracker.create_group("g")
        _seed_experiments(tracker, "g", 2)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_experiments_screen(
                app, facade, all_experiments=True
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            event = SimpleNamespace(data_table=table, label=Text("Duration"))
            screen.on_data_table_header_selected(event)
            await pilot.pause()
            assert screen._sort_by == "duration"
            assert screen._order == "desc"
            screen.on_data_table_header_selected(event)
            await pilot.pause()
            assert screen._order == "asc"
            # Unmapped columns (Sel / Tags / Group) are ignored.
            before = (screen._sort_by, screen._order)
            screen.on_data_table_header_selected(
                SimpleNamespace(data_table=table, label=Text("Sel"))
            )
            await pilot.pause()
            assert (screen._sort_by, screen._order) == before
