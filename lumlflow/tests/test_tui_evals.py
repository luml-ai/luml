"""Pilot tests for the Evals tab and the Eval detail screen.

Covers SPEC.md task: "Build the evals tab and eval detail screen" —
the experiment-detail Evals tab (table with dynamic columns derived
from `EvalColumns`, score heatmap, dataset selector, average scores
header, advanced filter editor with live validation, sort and lazy
pagination, drill-in), and the Eval detail screen (inputs/outputs/
refs/scores/metadata sections plus eval annotation CRUD).

All tests use Textual's headless `App.run_test()` + `Pilot` against an
in-memory seeded `ExperimentTracker` so the suite stays deterministic
and fast — no real filesystem store, no wall-clock waits.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.schemas.annotations import (
    AnnotationKind,
    AnnotationValueType,
    CreateAnnotation,
)
from lumlflow.tracker import ThreadSafeTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.eval_detail import EvalDetailScreen, _render_dict
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.screens.trace_detail import TraceDetailScreen
from lumlflow.tui.widgets.annotation_dialog import (
    AnnotationDialog,
    AnnotationDialogResult,
)
from lumlflow.tui.widgets.dialogs import (
    ConfirmDialog,
    FilterEditorDialog,
    SortChooserDialog,
)
from lumlflow.tui.widgets.evals_panel import (
    ALL_DATASETS,
    EvalsPanel,
    _format_score,
    _heatmap_style,
    _numeric_score,
)
from textual.widgets import DataTable, Input, ListView, Static

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    # The evals panel kicks off four worker threads concurrently
    # (datasets, columns, averages, page). The raw `ExperimentTracker`
    # shares a single SQLite connection across threads, which is unsafe
    # under simultaneous reads — the production TUI wraps the tracker in
    # `ThreadSafeTracker` for exactly this reason, so the tests must use
    # the same wrapper to mirror real behavior.
    return ThreadSafeTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade)


async def _wait_until(pilot, predicate, *, max_pauses: int = 80) -> bool:
    """Wait until `predicate()` is true or up to `max_pauses` pause cycles.

    Returns the final truthiness of the predicate. Worker threads in
    Textual settle asynchronously; a fixed number of pauses is a
    flake-prone way to wait for them to complete because pause cadence
    depends on the test scheduler. Each pause includes a small wall
    delay so blocking worker threads actually get CPU time between
    yields — otherwise an event-loop-only pause can return before the
    worker has had a chance to make progress.
    """

    for _ in range(max_pauses):
        try:
            if predicate():
                return True
        except Exception:
            pass
        await pilot.pause(0.01)
    try:
        return bool(predicate())
    except Exception:
        return False


def _seed_experiment_with_evals(
    tracker: ExperimentTracker,
    *,
    group: str = "g",
    name: str = "exp",
    samples: list[tuple[str, str, dict, dict | None, dict | None, dict | None]]
    | None = None,
) -> str:
    """Seed an experiment with several eval samples.

    `samples` is a list of
    `(eval_id, dataset_id, inputs, outputs, refs, scores)` tuples. By
    default it seeds three evals across two datasets with varied score
    ranges so the heatmap has data to color.
    """

    tracker.create_group(group)
    exp_id = tracker.start_experiment(name=name, group=group)
    if samples is None:
        samples = [
            (
                "e-1",
                "ds-1",
                {"prompt": "hello"},
                {"answer": "hi"},
                {"expected": "hi"},
                {"accuracy": 0.95, "latency_ms": 12},
            ),
            (
                "e-2",
                "ds-1",
                {"prompt": "world"},
                {"answer": "earth"},
                {"expected": "world"},
                {"accuracy": 0.3, "latency_ms": 50},
            ),
            (
                "e-3",
                "ds-2",
                {"prompt": "foo"},
                {"answer": "bar"},
                {"expected": "bar"},
                {"accuracy": 0.8, "latency_ms": 30},
            ),
        ]
    for eval_id, dataset_id, inputs, outputs, refs, scores in samples:
        tracker.log_eval_sample(
            eval_id=eval_id,
            dataset_id=dataset_id,
            inputs=inputs,
            outputs=outputs,
            references=refs,
            scores=scores,
            experiment_id=exp_id,
        )
    tracker.end_experiment(experiment_id=exp_id)
    return exp_id


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
# Pure helpers
# ---------------------------------------------------------------------------


class TestFormatScore:
    def test_none_returns_dash(self) -> None:
        assert _format_score(None) == "—"

    def test_int(self) -> None:
        assert _format_score(3) == "3"

    def test_float_three_decimals(self) -> None:
        assert _format_score(0.12345) == "0.123"

    def test_integer_float(self) -> None:
        assert _format_score(2.0) == "2"

    def test_bool(self) -> None:
        assert _format_score(True) == "true"
        assert _format_score(False) == "false"


class TestNumericScore:
    def test_int(self) -> None:
        assert _numeric_score(3) == 3.0

    def test_float(self) -> None:
        assert _numeric_score(0.5) == 0.5

    def test_bool_excluded(self) -> None:
        # Booleans must not be picked up as numeric scores (the heatmap
        # color would otherwise be meaningless for binary signals).
        assert _numeric_score(True) is None
        assert _numeric_score(False) is None

    def test_string_excluded(self) -> None:
        assert _numeric_score("hello") is None


class TestHeatmapStyle:
    def test_min_picks_first_stop(self) -> None:
        style = _heatmap_style(0.0, 0.0, 1.0)
        assert "red" in style
        assert "bold" in style

    def test_max_picks_last_stop(self) -> None:
        style = _heatmap_style(1.0, 0.0, 1.0)
        # The last stop in the palette is the highest score color.
        assert "cyan" in style or "green" in style
        assert "bold" in style

    def test_flat_range_uses_middle(self) -> None:
        # When all rows have the same score, no false gradient.
        style = _heatmap_style(0.5, 0.5, 0.5)
        assert style.startswith("bold ")

    def test_below_low_clamps(self) -> None:
        style = _heatmap_style(-0.5, 0.0, 1.0)
        assert "red" in style

    def test_above_high_clamps(self) -> None:
        # Should not crash and should resolve to the highest stop.
        style = _heatmap_style(2.0, 0.0, 1.0)
        assert "bold " in style


class TestRenderDict:
    def test_empty_dict_renders_none(self) -> None:
        text = _render_dict({})
        assert str(text) == "(none)"

    def test_none_renders_none(self) -> None:
        text = _render_dict(None)
        assert str(text) == "(none)"

    def test_renders_key_value(self) -> None:
        text = _render_dict({"a": 1, "b": "hi"})
        rendered = str(text)
        assert "a" in rendered and "1" in rendered
        assert "b" in rendered and "hi" in rendered

    def test_renders_bool(self) -> None:
        text = _render_dict({"x": True})
        rendered = str(text)
        assert "true" in rendered

    def test_renders_null(self) -> None:
        text = _render_dict({"x": None})
        rendered = str(text)
        assert "null" in rendered


# ---------------------------------------------------------------------------
# Evals tab — lazy load + columns + rows
# ---------------------------------------------------------------------------


class TestEvalsPanelListing:
    async def test_evals_tab_loads_on_activation(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            # Lazy: not started until the tab is activated.
            assert panel._started is False
            screen.action_jump_tab("evals")
            assert await _wait_until(pilot, lambda: len(panel._rows) == 3)
            assert panel._started is True
            table = panel.query_one("#evals-table", DataTable)
            assert table.row_count == 3
            keys = {r.key.value or "" for r in table.ordered_rows}
            assert keys == {"e-1", "e-2", "e-3"}

    async def test_columns_include_dynamic_keys(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Eval table columns are derived from `EvalColumns` so they
        include one column per input / output / score field."""

        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            # Wait until the columns worker has finished resolving the
            # dynamic key set so the assertion isn't tied to a fixed
            # number of pause cycles.
            assert await _wait_until(
                pilot,
                lambda: any(
                    cid.startswith("score.") for cid, _ in panel._column_order
                ),
            )
            col_ids = {cid for cid, _ in panel._column_order}
            assert "score.accuracy" in col_ids
            assert "score.latency_ms" in col_ids
            assert "input.prompt" in col_ids
            assert "output.answer" in col_ids
            assert "ref.expected" in col_ids
            # Static structural columns are always present.
            assert "__id__" in col_ids
            assert "__dataset__" in col_ids
            assert "__created__" in col_ids

    async def test_empty_state_shown_when_no_evals(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="empty", group="g")
        tracker.end_experiment(experiment_id=exp_id)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="empty"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            # Wait until the first page reports back (even if empty).
            assert await _wait_until(
                pilot, lambda: panel._started and not panel._loading
            )
            empty = panel.query_one("#evals-empty", Static)
            assert "No evals" in str(empty.render())


# ---------------------------------------------------------------------------
# Evals tab — heatmap coloring
# ---------------------------------------------------------------------------


class TestEvalsHeatmap:
    async def test_score_range_recomputed_after_load(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """The panel computes (low, high) per numeric score key after a
        page load so the heatmap colors the extremes correctly."""

        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: len(panel._rows) == 3)
            # Default seed has accuracy scores 0.95, 0.3, 0.8 → range
            # (0.3, 0.95). Latency: 12, 50, 30 → (12, 50).
            assert "accuracy" in panel._score_ranges
            low, high = panel._score_ranges["accuracy"]
            assert low == pytest.approx(0.3)
            assert high == pytest.approx(0.95)
            low2, high2 = panel._score_ranges["latency_ms"]
            assert low2 == 12
            assert high2 == 50

    async def test_score_cell_carries_heatmap_style(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: len(panel._rows) == 3)
            # The highest accuracy (0.95 → e-1) should render with the
            # last heatmap stop ("bold bright_cyan" in the current palette).
            top_row = next(r for r in panel._rows if r.key == "e-1")
            accuracy = (top_row.eval.scores or {})["accuracy"]
            cell = panel._render_score_cell("accuracy", accuracy)
            assert str(cell.style).startswith("bold ")


# ---------------------------------------------------------------------------
# Evals tab — dataset selector + averages
# ---------------------------------------------------------------------------


class TestEvalsDatasetSelector:
    async def test_dataset_list_populated(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: len(panel._dataset_ids) == 2)
            assert set(panel._dataset_ids) == {"ds-1", "ds-2"}
            ds_list = panel.query_one("#evals-dataset-list", ListView)
            # All datasets + one entry per dataset = 3.
            assert len(ds_list.children) == 3

    async def test_switching_dataset_narrows_rows(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Selecting a dataset reissues the page request scoped to it."""

        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: len(panel._rows) == 3)
            panel._selected_dataset = "ds-2"
            panel.load_first_page()
            assert await _wait_until(
                pilot, lambda: {r.key for r in panel._rows} == {"e-3"}
            )
            assert panel._selected_dataset == "ds-2"

    async def test_next_dataset_key_cycles_through_datasets(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """`d` cycles All → ds-1 → ds-2 → All without touching the mouse.

        There is no focus route to the dataset ListView (Tab cycles the
        screen's tabs), so the cycle key is the only keyboard path."""

        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(
                pilot, lambda: len(panel._rows) == 3 and len(panel._dataset_ids) == 2
            )
            panel.action_next_dataset()
            assert await _wait_until(
                pilot, lambda: panel._selected_dataset == "ds-1"
            )
            assert await _wait_until(
                pilot, lambda: {r.key for r in panel._rows} == {"e-1", "e-2"}
            )
            panel.action_next_dataset()
            assert await _wait_until(
                pilot, lambda: panel._selected_dataset == "ds-2"
            )
            assert await _wait_until(
                pilot, lambda: {r.key for r in panel._rows} == {"e-3"}
            )
            panel.action_next_dataset()
            assert await _wait_until(
                pilot, lambda: panel._selected_dataset is None
            )
            assert await _wait_until(pilot, lambda: len(panel._rows) == 3)

    async def test_prev_dataset_key_wraps_to_last(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(
                pilot, lambda: len(panel._rows) == 3 and len(panel._dataset_ids) == 2
            )
            panel.action_prev_dataset()
            assert await _wait_until(
                pilot, lambda: panel._selected_dataset == "ds-2"
            )

    async def test_average_scores_label_renders(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(
                pilot, lambda: "accuracy" in panel._average_scores
            )
            label = panel.query_one("#evals-avg-scores", Static)
            text = str(label.render())
            assert "accuracy" in text


# ---------------------------------------------------------------------------
# Evals tab — filter / sort dialogs
# ---------------------------------------------------------------------------


class TestEvalsFilterDialog:
    async def test_filter_dialog_opens(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: panel._started)
            panel.action_open_filter()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, FilterEditorDialog)
            )

    async def test_filter_validation_runs(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: panel._started)
            panel.action_open_filter()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, FilterEditorDialog)
            )
            dialog = app.screen
            assert isinstance(dialog, FilterEditorDialog)
            # Wait until the dialog has finished composing its widgets
            # so the validator can populate the inline note.
            assert await _wait_until(
                pilot,
                lambda: dialog.query("#filter-validation").first() is not None,
            )
            dialog._run_validation("not a valid filter")
            # Wait for the validation result to surface.
            assert await _wait_until(
                pilot,
                lambda: str(
                    dialog.query_one("#filter-validation", Static).render()
                ).startswith(("✓", "✗")),
            )

    async def test_sort_dialog_opens(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: panel._started)
            panel.action_open_sort()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, SortChooserDialog)
            )


# ---------------------------------------------------------------------------
# Evals tab — search
# ---------------------------------------------------------------------------


class TestEvalsSearch:
    async def test_search_field_toggles_visibility(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: panel._started)
            search = panel.query_one("#evals-search", Input)
            assert "-visible" not in search.classes
            panel.action_begin_search()
            await pilot.pause()
            assert "-visible" in search.classes


# ---------------------------------------------------------------------------
# Drill-in
# ---------------------------------------------------------------------------


class TestDrillInToEvalDetail:
    async def test_open_focused_pushes_eval_detail(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(
            tracker,
            samples=[
                ("only-1", "ds-1", {"x": 1}, {"y": 2}, None, {"score": 0.5}),
            ],
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: len(panel._rows) == 1)
            table = panel.query_one("#evals-table", DataTable)
            assert table.row_count == 1
            table.focus()
            await pilot.pause()
            panel.action_open_focused()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, EvalDetailScreen)
            )
            current = app.screen
            assert isinstance(current, EvalDetailScreen)
            assert current._eval_id == "only-1"
            assert current._dataset_id == "ds-1"


# ---------------------------------------------------------------------------
# Eval detail screen — content
# ---------------------------------------------------------------------------


class TestEvalDetailScreen:
    async def test_loads_eval_details(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            assert await _wait_until(pilot, lambda: screen._eval is not None)
            assert screen._eval is not None
            assert screen._eval.id == "e-1"
            inputs_static = screen.query_one("#eval-inputs", Static)
            text = str(inputs_static.render())
            assert "prompt" in text
            assert "hello" in text
            outputs_static = screen.query_one("#eval-outputs", Static)
            text = str(outputs_static.render())
            assert "answer" in text

    async def test_breadcrumb_includes_path(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp-name",
                group_name="grp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            await pilot.pause()
            labels = tuple(s.label for s in screen.breadcrumb_segments())
            assert labels[0] == "Groups"
            assert labels[1] == "grp"
            assert labels[2] == "exp-name"
            assert labels[3].startswith("Eval")


# ---------------------------------------------------------------------------
# Eval annotation CRUD via the eval detail screen
# ---------------------------------------------------------------------------


class TestEvalAnnotationCrud:
    async def test_annotate_opens_dialog(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            screen.action_annotate()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, AnnotationDialog)
            )

    async def test_create_annotation_round_trip(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            result = AnnotationDialogResult(
                mode="create",
                name="quality",
                kind=AnnotationKind.FEEDBACK,
                value_type=AnnotationValueType.BOOL,
                value=True,
                rationale="looks good",
            )
            screen._on_annotation_dialog_result(result)
            # Poll the handler-side state — it's the source of truth and
            # is unaffected by races between in-flight worker threads.
            assert await _wait_until(
                pilot,
                lambda: any(
                    a.name == "quality"
                    for a in (
                        facade.list_eval_annotations(
                            exp_id, "ds-1", "e-1"
                        ).unwrap()
                        or []
                    )
                ),
            )

    async def test_delete_annotation_confirm_dialog(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        facade.create_eval_annotation(
            exp_id,
            "ds-1",
            "e-1",
            CreateAnnotation(
                name="latency",
                annotation_kind=AnnotationKind.EXPECTATION,
                value_type=AnnotationValueType.INT,
                value=42,
                user="t",
            ),
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            assert await _wait_until(pilot, lambda: bool(screen._annotations))
            table = screen.query_one("#eval-annotations-table", DataTable)
            table.focus()
            await pilot.pause()
            screen.action_delete_annotation()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, ConfirmDialog)
            )

    async def test_delete_annotation_removes_row(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        created = facade.create_eval_annotation(
            exp_id,
            "ds-1",
            "e-1",
            CreateAnnotation(
                name="latency",
                annotation_kind=AnnotationKind.EXPECTATION,
                value_type=AnnotationValueType.INT,
                value=42,
                user="t",
            ),
        ).unwrap()
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            assert await _wait_until(pilot, lambda: bool(screen._annotations))
            screen._on_annotation_delete_confirmed(created.id, True)
            # Handler-side state is the source of truth.
            assert await _wait_until(
                pilot,
                lambda: all(
                    a.id != created.id
                    for a in (
                        facade.list_eval_annotations(
                            exp_id, "ds-1", "e-1"
                        ).unwrap()
                        or []
                    )
                ),
            )


# ---------------------------------------------------------------------------
# Evals tab — rendered layout
# ---------------------------------------------------------------------------


class TestEvalsTableLayout:
    async def test_table_gets_real_height_after_load(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Regression: the dataset ListView and the controls Vertical both
        default to `height: 1fr`, which made the auto-height controls bar
        swallow the whole panel — the table rendered 1 row tall (invisible)
        even though it held every eval. Assert on the *rendered* geometry,
        not the DataTable's internal row count."""

        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _push_detail_screen(
                app, facade, experiment_id=exp_id, experiment_name="exp"
            )
            await pilot.pause()
            await pilot.pause()
            screen.action_jump_tab("evals")
            panel = screen.query_one("#pane-evals-panel", EvalsPanel)
            assert await _wait_until(pilot, lambda: len(panel._rows) == 3)
            table = panel.query_one("#evals-table", DataTable)
            assert await _wait_until(pilot, lambda: table.region.height >= 5)
            controls = panel.query_one("#evals-controls")
            assert controls.region.height <= 10


# ---------------------------------------------------------------------------
# Eval → trace drill-in
# ---------------------------------------------------------------------------


def _seed_eval_linked_to_trace(
    tracker: ExperimentTracker, *, trace_id: str = "tr-1"
) -> str:
    tracker.create_group("g")
    exp_id = tracker.start_experiment(name="exp", group="g")
    tracker.log_span(
        trace_id=trace_id,
        span_id=f"{trace_id}-root",
        name="root",
        start_time_unix_nano=1_000_000,
        end_time_unix_nano=2_000_000,
        status_code=1,
        experiment_id=exp_id,
    )
    tracker.log_eval_sample(
        eval_id="e-1",
        dataset_id="ds-1",
        inputs={"prompt": "hello"},
        outputs={"answer": "hi"},
        scores={"accuracy": 0.9},
        experiment_id=exp_id,
    )
    tracker.link_eval_sample_to_trace(
        eval_dataset_id="ds-1",
        eval_id="e-1",
        trace_id=trace_id,
        experiment_id=exp_id,
    )
    tracker.end_experiment(experiment_id=exp_id)
    return exp_id


class TestEvalTraceDrillIn:
    async def test_open_trace_pushes_trace_detail(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_eval_linked_to_trace(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            assert await _wait_until(pilot, lambda: screen._eval is not None)
            screen.action_open_trace()
            assert await _wait_until(
                pilot, lambda: isinstance(app.screen, TraceDetailScreen)
            )
            current = app.screen
            assert isinstance(current, TraceDetailScreen)
            assert current._trace_id == "tr-1"

    async def test_open_trace_without_links_stays_on_detail(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_evals(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            assert await _wait_until(pilot, lambda: screen._eval is not None)
            screen.action_open_trace()
            await pilot.pause()
            await pilot.pause()
            assert app.screen is screen

    async def test_linked_traces_section_lists_trace_ids(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_eval_linked_to_trace(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = EvalDetailScreen(
                facade=facade,
                experiment_id=exp_id,
                experiment_name="exp",
                dataset_id="ds-1",
                eval_id="e-1",
            )
            app.push_screen(screen)
            assert await _wait_until(pilot, lambda: screen._eval is not None)
            traces_static = screen.query_one("#eval-traces", Static)
            text = str(traces_static.render())
            assert "tr-1" in text


# ---------------------------------------------------------------------------
# ALL_DATASETS sentinel
# ---------------------------------------------------------------------------


class TestAllDatasetsSentinel:
    def test_value_is_distinct_from_dataset_ids(self) -> None:
        # Real dataset ids should never collide with the sentinel.
        assert ALL_DATASETS.startswith("__")
