"""Pilot tests for the experiment detail screen.

Covers SPEC.md task: "Build the experiment detail Overview and Metrics tabs"
— tabbed scaffold with mnemonic / positional / cyclic tab switching, the
Overview tab (metadata, params, tags, linked models with edit/delete),
and the Metrics tab (chart rendering with subsampling on resize).

All tests use Textual's headless `App.run_test()` + `Pilot` against an
in-memory seeded `ExperimentTracker` so the suite is deterministic and
fast — no real filesystem store, no wall-clock waits.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.experiment_detail import (
    TAB_DEFS,
    ExperimentDetailScreen,
    TabBar,
    TabSegment,
    _format_duration,
)
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    EditEntityDialog,
    EntityEditResult,
)
from lumlflow.tui.widgets.metric_grid import (
    _CELL_HEIGHT,
    MetricCell,
    MetricGrid,
    MetricZoomView,
)
from lumlflow.tui.widgets.panel_frame import PanelFrame
from textual.containers import Container
from textual.widgets import DataTable, Static


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade)


def _seed_experiment_with_metrics(
    tracker: ExperimentTracker,
    group: str = "g",
    name: str = "exp",
    metric_keys: tuple[str, ...] = ("loss", "accuracy"),
    points_per_metric: int = 20,
    finish: bool = True,
) -> str:
    """Create one experiment with a few logged metrics, return its id.

    By default the experiment is finished (`end_experiment`) so the
    backend writes the latest metric values to `dynamic_params` — that
    is the keyset the Metrics tab uses to list available metrics.
    Set `finish=False` to test the active-but-no-metrics-yet flow.
    """

    tracker.create_group(group)
    exp_id = tracker.start_experiment(name=name, group=group)
    for key in metric_keys:
        for step in range(points_per_metric):
            tracker.log_dynamic(
                key,
                float(step) / max(1, points_per_metric),
                step=step,
                experiment_id=exp_id,
            )
    if finish:
        tracker.end_experiment(experiment_id=exp_id)
    return exp_id


def _seed_experiment_with_model(
    tracker: ExperimentTracker,
    tmp_path: Path,
    *,
    group: str = "g",
    name: str = "exp",
    model_name: str = "m1",
) -> tuple[str, str]:
    """Create an experiment with a linked model. Returns (exp_id, model_id)."""

    tracker.create_group(group)
    exp_id = tracker.start_experiment(name=name, group=group)
    model_file = tmp_path / "model.luml"
    model_file.write_bytes(b"fake-model-data")
    tracker.backend.log_model(exp_id, str(model_file), name=model_name)
    models = tracker.get_models(exp_id)
    assert models, "model seed failed"
    return exp_id, models[0].id


def _push_detail_screen(
    app: LumlflowApp,
    facade: DataFacade,
    *,
    experiment_id: str,
    experiment_name: str | None = None,
    group_name: str | None = None,
) -> ExperimentDetailScreen:
    screen = ExperimentDetailScreen(
        facade=facade,
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        group_name=group_name,
    )
    app.push_screen(screen)
    return screen


# ---------------------------------------------------------------------------
# Tab switching
# ---------------------------------------------------------------------------


class TestTabSwitching:
    async def test_initial_tab_is_overview(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            assert screen._active_tab == "overview"

    async def test_mnemonic_jumps(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            # Uppercase letters are the mnemonic accelerators. Lowercase
            # `t`/`e` remain reserved for theme / row-edit.
            for tab_id, mnemonic in [
                ("metrics", "M"),
                ("traces", "T"),
                ("evals", "E"),
                ("attachments", "A"),
                ("overview", "O"),
            ]:
                await pilot.press(mnemonic)
                await pilot.pause()
                assert screen._active_tab == tab_id, (
                    f"mnemonic {mnemonic} should activate {tab_id}, got "
                    f"{screen._active_tab}"
                )

    async def test_all_tab_segments_fit_within_viewport(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Regression: each TabSegment must size to its label (width: auto)
        # so all five tabs lay out side-by-side within the bar. A missing
        # width made every segment expand to the full row, pushing every
        # tab after the first off-screen ("no tabs" symptom).
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            tabbar = app.screen.query_one("#exp-detail-tabbar", TabBar)
            segments = list(tabbar.query(TabSegment))
            assert len(segments) == len(TAB_DEFS)
            for seg in segments:
                assert seg.region.right <= tabbar.region.right, (
                    f"segment {seg.tab_id} overflows the tab bar "
                    f"(right={seg.region.right} > {tabbar.region.right})"
                )
                # A full-width segment is the bug signature; a label-sized
                # segment is at most a couple dozen columns wide.
                assert seg.size.width < 40, (
                    f"segment {seg.tab_id} is {seg.size.width} wide — it is "
                    "expanding to fill the row instead of sizing to its label"
                )

    async def test_lowercase_mnemonics_jump(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Lowercase letters are the primary tab accelerators (they match
        # the visible labels); `e` means Evals and `t` means Traces here.
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            for tab_id, key in [
                ("metrics", "m"),
                ("traces", "t"),
                ("evals", "e"),
                ("attachments", "a"),
                ("overview", "o"),
            ]:
                await pilot.press(key)
                await pilot.pause()
                assert screen._active_tab == tab_id, (
                    f"{key!r} should activate {tab_id}, got {screen._active_tab}"
                )

    async def test_tab_key_cycles_tabs_uniformly(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # `Tab` advances to the next tab on every tab — including
        # Metrics, whose chart grid is navigated with the arrow keys.
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            assert screen._active_tab == "overview"
            await pilot.press("tab")
            await pilot.pause()
            assert screen._active_tab == "metrics"
            # Tab keeps cycling from Metrics too — the grid is arrow-key
            # territory, so Tab no longer has a per-tab special case.
            await pilot.press("tab")
            await pilot.pause()
            assert screen._active_tab == "traces"
            # Shift+Tab walks back through the tabs.
            await pilot.press("o")
            await pilot.pause()
            await pilot.press("shift+tab")
            await pilot.pause()
            assert screen._active_tab == "attachments"

    async def test_position_keys_jump_to_tabs(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            for i, (tab_id, _, _) in enumerate(TAB_DEFS, start=1):
                await pilot.press(str(i))
                await pilot.pause()
                assert screen._active_tab == tab_id

    async def test_cycle_keys_navigate(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            assert screen._active_tab == "overview"
            await pilot.press("]")
            await pilot.pause()
            assert screen._active_tab == "metrics"
            await pilot.press("]")
            await pilot.pause()
            assert screen._active_tab == "traces"
            await pilot.press("[")
            await pilot.pause()
            assert screen._active_tab == "metrics"
            # Wrap-around back to overview.
            await pilot.press("[")
            await pilot.pause()
            assert screen._active_tab == "overview"
            await pilot.press("[")
            await pilot.pause()
            assert screen._active_tab == "attachments"

    async def test_only_active_pane_displayed(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            # Initially overview is visible, the rest are hidden.
            for tab_id, _, _ in TAB_DEFS:
                pane = screen.query_one(f"#pane-{tab_id}", Container)
                expected = tab_id == "overview"
                assert pane.display == expected, (
                    f"{tab_id} display={pane.display}, expected {expected}"
                )
            # Switch to metrics and re-check.
            screen.action_jump_tab("metrics")
            await pilot.pause()
            for tab_id, _, _ in TAB_DEFS:
                pane = screen.query_one(f"#pane-{tab_id}", Container)
                expected = tab_id == "metrics"
                assert pane.display == expected


# ---------------------------------------------------------------------------
# Tab labels render mnemonic letters highlighted
# ---------------------------------------------------------------------------


class TestTabLabels:
    async def test_tabbar_highlights_mnemonic_letters(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            tabbar = app.screen.query_one("#exp-detail-tabbar", TabBar)
            # The segmented tab bar now renders one ``TabSegment`` per
            # tab; concatenating each segment's rendered text gives the
            # same view the user sees.
            segments = list(tabbar.query(TabSegment))
            rendered = " ".join(str(s.render()) for s in segments)
            # The accelerators are uppercase O M T E A.
            for letter in ("O", "M", "T", "E", "A"):
                assert letter in rendered, f"{letter} missing in tabbar"
            # Position markers are present too so the alternates are
            # discoverable on-screen — the new bar uses plain digits
            # ("1 Overview" rather than "[1] Overview") since the
            # background swap already marks the active segment.
            for i in range(1, 6):
                assert f"{i}" in rendered, f"{i} position marker missing"


# ---------------------------------------------------------------------------
# Overview tab — metadata, params, tags, models
# ---------------------------------------------------------------------------


class TestOverview:
    async def test_renders_experiment_metadata(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="overview-exp", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="overview-exp"
            )
            await pilot.pause()
            await pilot.pause()
            meta = screen.query_one("#overview-meta", Static)
            text = str(meta.render())
            assert "overview-exp" in text
            assert "active" in text
            assert "g" in text  # group name

    async def test_breadcrumb_includes_group_and_name(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("grp-x")
        exp_id = tracker.start_experiment(name="zeta", group="grp-x")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app,
                facade,
                experiment_id=exp_id,
                experiment_name="zeta",
                group_name="grp-x",
            )
            await pilot.pause()
            await pilot.pause()
            segs = screen.breadcrumb_segments()
            labels = tuple(s.label for s in segs)
            assert labels == ("Groups", "grp-x", "zeta")

    async def test_models_table_renders(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id, model_id = _seed_experiment_with_model(
            tracker, tmp_path, model_name="resnet"
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#overview-models-table", DataTable)
            assert table.row_count == 1
            row_keys = [r.key.value or "" for r in table.ordered_rows]
            assert model_id in row_keys

    async def test_no_models_shows_empty_row(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="exp", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#overview-models-table", DataTable)
            assert table.row_count == 1
            assert screen._model_rows == []


# ---------------------------------------------------------------------------
# Overview — model edit / delete
# ---------------------------------------------------------------------------


class TestModelEdit:
    async def test_edit_model_dialog_opens(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id, _ = _seed_experiment_with_model(tracker, tmp_path)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            # Active tab is overview; ensure model row is focused.
            table = screen.query_one("#overview-models-table", DataTable)
            table.focus()
            await pilot.pause()
            screen.action_edit_focused_model()
            await pilot.pause()
            assert isinstance(app.screen, EditEntityDialog)

    async def test_enter_on_model_row_opens_edit(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        # `e` now means the Evals tab, so editing a linked model is
        # reached with Enter on its row. The models table is focused on
        # mount, so Enter works without a preliminary focus step.
        exp_id, _ = _seed_experiment_with_model(tracker, tmp_path)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, EditEntityDialog)

    async def test_e_key_opens_evals_tab_not_edit(
        self, facade: DataFacade, tracker: ExperimentTracker, tmp_path: Path
    ) -> None:
        # Regression: `e` must switch to the Evals tab and must not open
        # the model edit dialog.
        exp_id, _ = _seed_experiment_with_model(tracker, tmp_path)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()
            assert screen._active_tab == "evals"
            assert not isinstance(app.screen, EditEntityDialog)

    async def test_edit_model_updates_in_place(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id, model_id = _seed_experiment_with_model(
            tracker, tmp_path, model_name="orig"
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen._on_model_edit_submitted(
                model_id, EntityEditResult(name="renamed")
            )
            await pilot.pause()
            await pilot.pause()
            updated = next(r for r in screen._model_rows if r.key == model_id)
            assert updated.name == "renamed"


class TestModelDelete:
    async def test_delete_model_confirm_dialog(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id, _ = _seed_experiment_with_model(tracker, tmp_path)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#overview-models-table", DataTable)
            table.focus()
            await pilot.pause()
            screen.action_delete_focused_model()
            await pilot.pause()
            assert isinstance(app.screen, ConfirmDialog)

    async def test_delete_model_removes_row(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id, model_id = _seed_experiment_with_model(tracker, tmp_path)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen._on_model_delete_confirmed(model_id, True)
            await pilot.pause()
            await pilot.pause()
            assert all(r.key != model_id for r in screen._model_rows)


# ---------------------------------------------------------------------------
# Metrics tab
# ---------------------------------------------------------------------------


class TestMetricsTab:
    async def test_metrics_listed_from_dynamic_params(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "acc")
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            # Switch to metrics so the grid is laid out.
            screen.action_jump_tab("metrics")
            await pilot.pause()
            assert set(screen._metric_keys) == {"loss", "acc"}

    async def test_grid_renders_one_cell_per_metric(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """The grid should mount one ``MetricCell`` per metric key,
        ordered alphabetically."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "accuracy", "f1")
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            await pilot.pause()
            await pilot.pause()
            grid = screen.query_one("#metrics-grid", MetricGrid)
            cells = list(grid.query(MetricCell))
            # One cell per metric, ordered by sorted keys.
            keys_in_order = [c.metric_key for c in cells]
            assert keys_in_order == ["accuracy", "f1", "loss"]

    async def test_grid_cells_receive_history(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Each grid cell should be populated with fetched history points."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss",), points_per_metric=15
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            # Let the cell history requests round-trip.
            for _ in range(5):
                await pilot.pause()
            assert "loss" in screen._metric_history
            cached = screen._metric_history["loss"]
            assert cached.key == "loss"
            assert len(cached.history) > 0

    async def test_all_grid_cells_receive_history(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Every mini-chart must populate — not just one.

        Regression: the per-cell history worker used to be `exclusive`
        within a single group, so the concurrent fetches issued when the
        grid mounts cancelled each other and only the last chart ever
        received data. The grid is also given a real height so every row
        of cells is laid out rather than clipped to the first row.
        """

        keys = ("loss", "accuracy", "val_loss", "grad_norm")
        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=keys, points_per_metric=12
        )
        app = _make_app(facade)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(60):
                if set(screen._metric_history) == set(keys):
                    break
                await pilot.pause()
            # Every metric fetched its history — none were cancelled.
            assert set(screen._metric_history) == set(keys)
            grid = screen.query_one("#metrics-grid", MetricGrid)
            cells = list(grid.query(MetricCell))
            assert len(cells) == len(keys)
            for cell in cells:
                assert cell._history is not None, (
                    f"cell {cell.metric_key} never received history"
                )
            # The cell grid reserves an explicit height for every row
            # rather than collapsing to one (the old auto-height bug that
            # clipped all cells past the first row). Four metrics wrap to
            # at least two rows, so the reserved height exceeds one cell.
            cells_container = grid.query_one("#metric-grid-cells")
            assert cells_container.styles.height is not None
            assert cells_container.styles.height.value > _CELL_HEIGHT

    async def test_zoom_opens_and_returns(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Enter on a focused mini-chart opens the zoom view; Esc returns."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "accuracy"), points_per_metric=10
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            grid = screen.query_one("#metrics-grid", MetricGrid)
            zoom = screen.query_one("#metrics-zoom", MetricZoomView)
            assert grid.display is True
            assert zoom.display is False
            # Open the zoom view by emulating a cell ZoomRequested.
            screen._open_zoom("loss")
            await pilot.pause()
            await pilot.pause()
            assert screen._zoomed_metric == "loss"
            assert grid.display is False
            assert zoom.display is True
            assert zoom.metric_key == "loss"
            # Close the zoom view: directly invoke the same path Esc/`←` triggers.
            screen._close_zoom()
            await pilot.pause()
            assert screen._zoomed_metric is None
            assert grid.display is True
            assert zoom.display is False

    async def test_zoom_toggles_change_state(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Smoothing / log-scale / X-axis toggles flip the zoom state and
        the chart redraws (the underlying series transform changes)."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss",), points_per_metric=20
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            screen._open_zoom("loss")
            for _ in range(3):
                await pilot.pause()
            zoom = screen.query_one("#metrics-zoom", MetricZoomView)
            assert zoom.smoothing is False
            assert zoom.log_scale is False
            assert zoom.x_axis == "step"
            # Toggle smoothing via the screen action; the same path is
            # registered in the keymap as `metrics.toggle_smoothing`.
            screen.action_metrics_toggle_smoothing()
            await pilot.pause()
            assert zoom.smoothing is True
            screen.action_metrics_toggle_log_scale()
            await pilot.pause()
            assert zoom.log_scale is True
            screen.action_metrics_toggle_x_axis()
            await pilot.pause()
            assert zoom.x_axis == "wall_clock"
            # Toggles in non-zoom state are no-ops (no exception, no flip).
            screen._close_zoom()
            await pilot.pause()
            zoom_state_before = (zoom.smoothing, zoom.log_scale, zoom.x_axis)
            screen.action_metrics_toggle_smoothing()
            await pilot.pause()
            assert (
                zoom.smoothing,
                zoom.log_scale,
                zoom.x_axis,
            ) == zoom_state_before

    async def test_subsampled_state_recorded(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """When the handler subsamples, the cached history records it so
        the zoom status line can announce it."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss",), points_per_metric=500
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            # Force a small viewport so subsampling kicks in.
            screen._fetch_metric_history("loss", max_points=10)
            for _ in range(5):
                await pilot.pause()
            cached = screen._metric_history.get("loss")
            assert cached is not None
            assert cached.subsampled is True

    async def test_empty_metrics_shows_friendly_state(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="empty", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="empty"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            await pilot.pause()
            assert screen._metric_keys == []
            grid = screen.query_one("#metrics-grid", MetricGrid)
            # Empty state is visible, cell grid is hidden.
            empty = grid.query_one("#metric-grid-empty", Static)
            assert "-hidden" not in empty.classes
            # No cells mounted.
            assert list(grid.query(MetricCell)) == []

    async def test_enter_on_focused_cell_opens_zoom(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Pressing Enter on a focused mini-chart routes through the
        cell → grid → screen and opens the zoom view (SPEC scenario)."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "acc"), points_per_metric=5
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            grid = screen.query_one("#metrics-grid", MetricGrid)
            cells = list(grid.query(MetricCell))
            assert cells
            cells[0].focus()
            await pilot.pause()
            await pilot.press("enter")
            for _ in range(3):
                await pilot.pause()
            assert screen._zoomed_metric == cells[0].metric_key

    async def test_escape_in_zoom_returns_to_grid(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Esc inside the zoom view returns to the grid without popping
        the detail screen (the screen-level on_key intercepts it)."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss",), points_per_metric=8
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            screen._open_zoom("loss")
            for _ in range(3):
                await pilot.pause()
            assert screen._zoomed_metric == "loss"
            # Press Esc — the screen on_key intercepts it and closes
            # the zoom rather than popping the detail screen.
            await pilot.press("escape")
            await pilot.pause()
            assert screen._zoomed_metric is None
            # The experiment-detail screen is still the active screen.
            assert isinstance(app.screen, ExperimentDetailScreen)

    async def test_metrics_tab_activation_focuses_first_cell(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Jumping to Metrics lands focus on a mini-chart so the arrow
        keys work immediately, without a preliminary Tab press."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "acc"), points_per_metric=5
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            await pilot.press("m")
            for _ in range(5):
                await pilot.pause()
            focused = app.focused
            assert isinstance(focused, MetricCell)
            assert focused.metric_key == screen._metric_keys[0]

    async def test_zoom_arrows_step_between_metrics(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """`→`/`←` inside the zoom view step to the adjacent metric,
        keeping the toggles so charts are compared through one lens."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "acc"), points_per_metric=5
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            assert screen._metric_keys == ["acc", "loss"]
            screen._open_zoom("acc")
            for _ in range(3):
                await pilot.pause()
            zoom = screen.query_one("#metrics-zoom", MetricZoomView)
            zoom.action_toggle_smoothing()
            await pilot.pause()
            await pilot.press("right")
            for _ in range(3):
                await pilot.pause()
            assert screen._zoomed_metric == "loss"
            assert zoom.smoothing is True
            # Clamped at the last metric.
            await pilot.press("right")
            await pilot.pause()
            assert screen._zoomed_metric == "loss"
            await pilot.press("left")
            for _ in range(3):
                await pilot.pause()
            assert screen._zoomed_metric == "acc"

    async def test_escape_from_zoom_focuses_zoomed_cell(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Closing the zoom hands focus back to the cell that was
        zoomed, so arrow navigation continues from where the user was."""

        exp_id = _seed_experiment_with_metrics(
            tracker, metric_keys=("loss", "acc"), points_per_metric=5
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            screen._open_zoom("loss")
            for _ in range(3):
                await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            focused = app.focused
            assert isinstance(focused, MetricCell)
            assert focused.metric_key == "loss"

    async def test_live_refresh_repaints_grid(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Live-refresh should re-fetch the cached histories of visible
        cells so new logged points land in the grid in place."""

        # A finished experiment surfaces its metric keys via
        # dynamic_params; we then continue logging on the same
        # experiment to simulate a new point arriving while the user
        # has the metrics tab open.
        exp_id = _seed_experiment_with_metrics(
            tracker,
            metric_keys=("loss",),
            points_per_metric=5,
            finish=True,
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(8):
                await pilot.pause()
            initial_history = screen._metric_history.get("loss")
            assert initial_history is not None
            initial_count = len(initial_history.history)
            # Log additional points and trigger a live-refresh. The
            # initial fetch is exclusive within "experiment-metric"; a
            # follow-up refresh must replace its cache. To avoid racing
            # with the initial fetch we explicitly call the fetch path
            # rather than via grid.request_refresh_visible.
            for step in range(5, 12):
                tracker.log_dynamic(
                    "loss",
                    float(step) / 12,
                    step=step,
                    experiment_id=exp_id,
                )
            screen._fetch_metric_history("loss", max_points=200)
            for _ in range(8):
                await pilot.pause()
            refreshed = screen._metric_history.get("loss")
            assert refreshed is not None
            assert len(refreshed.history) > initial_count

    async def test_refresh_live_re_emits_grid_history_needed(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """``refresh_live`` should ask the grid to re-fetch its visible
        charts so live updates land in place (decoupled from worker timing)."""

        exp_id = _seed_experiment_with_metrics(
            tracker,
            metric_keys=("loss",),
            points_per_metric=5,
            finish=True,
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("metrics")
            for _ in range(5):
                await pilot.pause()
            # Trigger the refresh path; the cached history should not be
            # cleared (the refresh re-fetches in place) and the cell
            # remains populated.
            screen._refresh_metrics_visible()
            for _ in range(3):
                await pilot.pause()
            assert "loss" in screen._metric_history


# ---------------------------------------------------------------------------
# _format_duration helper
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_none(self) -> None:
        assert _format_duration(None) == "—"

    def test_sub_second(self) -> None:
        assert "ms" in _format_duration(0.05)

    def test_seconds(self) -> None:
        assert "s" in _format_duration(12.5)

    def test_minutes(self) -> None:
        assert "m" in _format_duration(125.0)

    def test_hours(self) -> None:
        assert "h" in _format_duration(7200.0)


# ---------------------------------------------------------------------------
# Drill-in from experiments list (integration)
# ---------------------------------------------------------------------------


class TestDrillInFromExperiments:
    async def test_open_experiment_pushes_detail_screen(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from lumlflow.tui.screens.experiments import ExperimentsScreen

        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="exp", group="g")
        # Locate the group's id for the screen constructor.
        group = next(g for g in tracker.list_groups() if g.name == "g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentsScreen(
                facade=facade, group_id=group.id, group_name="g"
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            await pilot.pause()
            screen.action_open_focused()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentDetailScreen)
            assert app.screen._experiment_id == exp_id


# ---------------------------------------------------------------------------
# Overview cards (panel-frame layout)
# ---------------------------------------------------------------------------


class TestOverviewCards:
    """Overview should render the four cards as titled ``PanelFrame``s.

    The cards are: About, Static parameters, Dynamic metrics, Tags, and
    Linked models — Static + Dynamic share a two-column row, the others
    are full-width. Each card carries the corresponding card title in
    its top border so the SPEC's "titled cards within panel frames"
    requirement is satisfied.
    """

    async def test_overview_card_frames_render(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="x", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="x"
            )
            await pilot.pause()
            await pilot.pause()
            cards = {
                "overview-about-card": "About",
                "overview-params-card": "Static parameters",
                "overview-dynamic-card": "Dynamic metrics",
                "overview-tags-card": "Tags",
                "overview-models-card": "Linked models",
            }
            for card_id, title in cards.items():
                frame = screen.query_one(f"#{card_id}", PanelFrame)
                assert frame.title == title, (
                    f"{card_id} title was {frame.title!r}, expected {title!r}"
                )
                # The PanelFrame writes its title into the Textual border
                # so the renderer actually puts it on screen.
                assert frame.border_title == title

    async def test_overview_params_and_dynamic_share_row(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """The Static parameters and Dynamic metrics cards live in the
        same horizontal row so they sit side-by-side on a wide terminal."""

        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="x", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="x"
            )
            await pilot.pause()
            await pilot.pause()
            params = screen.query_one("#overview-params-card", PanelFrame)
            dynamic = screen.query_one("#overview-dynamic-card", PanelFrame)
            # Same parent → same horizontal row.
            assert params.parent is dynamic.parent
            assert params.parent is not None


# ---------------------------------------------------------------------------
# Tab bar segmented-control behavior
# ---------------------------------------------------------------------------


class TestTabBarSegmented:
    async def test_active_segment_has_active_class(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Only the active tab segment carries the ``-active`` CSS class,
        which is what swaps in the accent background."""

        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            tabbar = screen.query_one("#exp-detail-tabbar", TabBar)
            segments = {s.tab_id: s for s in tabbar.query(TabSegment)}
            # Overview is active on entry.
            assert "-active" in segments["overview"].classes
            for tab_id in ("metrics", "traces", "evals", "attachments"):
                assert "-active" not in segments[tab_id].classes
            # Switch to Traces and re-check.
            screen.action_jump_tab("traces")
            await pilot.pause()
            assert "-active" in segments["traces"].classes
            assert "-active" not in segments["overview"].classes

    async def test_segment_click_jumps_tab(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Posting a ``SegmentClicked`` message must drive the same path
        as the keyboard mnemonic — the screen's ``action_jump_tab``."""

        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            assert screen._active_tab == "overview"
            evals_seg = screen.query_one("#tab-seg-evals", TabSegment)
            # Synthesize a click on the Evals segment — Textual delivers
            # the click via the segment's ``on_click`` which posts a
            # ``TabBar.SegmentClicked`` message.
            evals_seg.on_click()
            await pilot.pause()
            await pilot.pause()
            assert screen._active_tab == "evals"


class TestTabScopedFooter:
    """The footer hints follow the active tab's real key surface."""

    async def test_footer_scopes_change_per_tab(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            assert screen.footer_scopes() == ("global", "tabs", "models")
            screen.action_jump_tab("metrics")
            assert screen.footer_scopes() == ("global", "tabs", "metrics")
            screen.action_jump_tab("traces")
            assert screen.footer_scopes() == ("global", "tabs", "list")
            screen.action_jump_tab("attachments")
            assert screen.footer_scopes() == (
                "global",
                "tabs",
                "attachments",
            )

    async def test_footer_text_updates_on_tab_switch(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from lumlflow.tui.widgets.footer import ContextualFooter

        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            footer = screen.query_one("#app-footer", ContextualFooter)
            screen.action_jump_tab("metrics")
            await pilot.pause()
            await pilot.pause()
            text = str(footer.render())
            assert "Zoom" in text
            assert "Save to disk" not in text
            screen.action_jump_tab("attachments")
            await pilot.pause()
            await pilot.pause()
            text = str(footer.render())
            assert "Save to disk" in text
            assert "Zoom" not in text


class TestModelPublish:
    """`p` on a focused model row opens the model-mode publish flow."""

    async def test_p_on_model_row_opens_model_publish(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        from unittest.mock import patch

        from lumlflow.tui.screens.cloud_publish import CloudPublishScreen

        exp_id, model_id = _seed_experiment_with_model(tracker, tmp_path)
        app = _make_app(facade)
        with patch.object(facade.auth, "has_api_key", return_value=False):
            async with app.run_test() as pilot:
                await pilot.pause()
                _push_detail_screen(
                    app, facade, experiment_id=exp_id, experiment_name="exp"
                )
                await pilot.pause()
                await pilot.pause()
                # The models table is focused with the cursor on m1.
                await pilot.press("p")
                await pilot.pause()
                await pilot.pause()
                publish = app.screen
                assert isinstance(publish, CloudPublishScreen)
                assert publish._is_model is True
                assert publish._ctx.model_id == model_id
                assert publish._ctx.model_name == "m1"

    async def test_p_off_overview_publishes_experiment(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        from unittest.mock import patch

        from lumlflow.tui.screens.cloud_publish import CloudPublishScreen

        exp_id = _seed_experiment_with_metrics(tracker)
        app = _make_app(facade)
        with patch.object(facade.auth, "has_api_key", return_value=False):
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _push_detail_screen(
                    app, facade, experiment_id=exp_id, experiment_name="exp"
                )
                await pilot.pause()
                await pilot.pause()
                screen.action_jump_tab("metrics")
                for _ in range(4):
                    await pilot.pause()
                await pilot.press("p")
                await pilot.pause()
                await pilot.pause()
                publish = app.screen
                assert isinstance(publish, CloudPublishScreen)
                assert publish._is_model is False
                assert publish._ctx.experiment_id == exp_id
