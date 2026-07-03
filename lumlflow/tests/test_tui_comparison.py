"""Pilot tests for the experiment comparison screen.

Covers SPEC.md task: "Add the comparison screen" — multi-select of
experiments, ComparisonScreen with the static-param diff table
(differences highlighted), overlaid multi-series metric chart, and
eval score comparison by dataset.

All tests use Textual's headless `App.run_test()` + `Pilot` against an
in-memory seeded `ExperimentTracker` so the suite is deterministic and
fast — no real filesystem store, no wall-clock waits.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.schemas.experiments import (
    ExperimentDetails,
    ExperimentStatus,
)
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.comparison import (
    ComparisonScreen,
    _diff_static_params,
    _rich_color_for,
    _shared_metric_keys,
)
from lumlflow.tui.screens.experiments import ExperimentsScreen
from lumlflow.tui.widgets.panel_frame import PanelFrame
from textual.widgets import DataTable, ListView, Static


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade)


def _seed_experiment(
    tracker: ExperimentTracker,
    *,
    group: str = "g",
    name: str = "exp",
    static_params: dict | None = None,
    metric_series: dict[str, list[tuple[int, float]]] | None = None,
    evals: list[tuple[str, str, dict, dict, dict, dict]] | None = None,
    finish: bool = True,
) -> str:
    """Create one experiment with static params, metrics, and optionally evals.

    `static_params`  — dict[str, Any] logged via `log_static`
    `metric_series`  — dict[key, list[(step, value)]] logged via `log_dynamic`
    `evals`          — list of (eval_id, dataset_id, inputs, outputs, refs, scores)
    """

    tracker.create_group(group)
    exp_id = tracker.start_experiment(name=name, group=group)
    if static_params:
        for k, v in static_params.items():
            tracker.log_static(k, v, experiment_id=exp_id)
    if metric_series:
        for key, points in metric_series.items():
            for step, value in points:
                tracker.log_dynamic(
                    key, value, step=step, experiment_id=exp_id
                )
    if evals:
        for eval_id, dataset_id, inputs, outputs, refs, scores in evals:
            tracker.log_eval_sample(
                eval_id=eval_id,
                dataset_id=dataset_id,
                inputs=inputs,
                outputs=outputs,
                references=refs,
                scores=scores,
                experiment_id=exp_id,
            )
    if finish:
        tracker.end_experiment(experiment_id=exp_id)
    return exp_id


def _fetch_details(facade: DataFacade, experiment_id: str):
    """Pull `ExperimentDetails` for the given id via the facade."""

    return facade.get_experiment(experiment_id).unwrap()


def _push_comparison(
    app: LumlflowApp,
    facade: DataFacade,
    experiments,
) -> ComparisonScreen:
    screen = ComparisonScreen(facade=facade, experiments=experiments)
    app.push_screen(screen)
    return screen


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestDiffStaticParams:
    """`_diff_static_params` mirrors the static-param diff table."""

    def test_empty_when_no_params(self) -> None:
        exps = [
            ExperimentDetails(
                id="a",
                name="a",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
            ),
            ExperimentDetails(
                id="b",
                name="b",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
            ),
        ]
        assert _diff_static_params(exps) == []

    def test_identical_params_marked_same(self) -> None:
        exps = [
            ExperimentDetails(
                id="a",
                name="a",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                static_params={"lr": 0.01, "bs": 32},
            ),
            ExperimentDetails(
                id="b",
                name="b",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                static_params={"lr": 0.01, "bs": 32},
            ),
        ]
        rows = _diff_static_params(exps)
        # Sorted by key, so bs first then lr.
        assert [r.key for r in rows] == ["bs", "lr"]
        assert all(not r.differs for r in rows)

    def test_differing_value_marked_differs(self) -> None:
        exps = [
            ExperimentDetails(
                id="a",
                name="a",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                static_params={"lr": 0.01, "bs": 32},
            ),
            ExperimentDetails(
                id="b",
                name="b",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                static_params={"lr": 0.001, "bs": 32},
            ),
        ]
        rows = {r.key: r for r in _diff_static_params(exps)}
        assert rows["lr"].differs is True
        assert rows["bs"].differs is False

    def test_missing_key_marked_differs(self) -> None:
        exps = [
            ExperimentDetails(
                id="a",
                name="a",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                static_params={"lr": 0.01, "extra": 1},
            ),
            ExperimentDetails(
                id="b",
                name="b",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                static_params={"lr": 0.01},
            ),
        ]
        rows = {r.key: r for r in _diff_static_params(exps)}
        # `extra` exists for one and is None for the other → differs.
        assert rows["extra"].differs is True
        assert rows["lr"].differs is False


class TestSharedMetricKeys:
    def test_union_across_experiments(self) -> None:
        exps = [
            ExperimentDetails(
                id="a",
                name="a",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                dynamic_params={"loss": 0.1, "acc": 0.9},
            ),
            ExperimentDetails(
                id="b",
                name="b",
                status=ExperimentStatus.COMPLETED,
                created_at=datetime.now(),
                dynamic_params={"loss": 0.2, "f1": 0.8},
            ),
        ]
        assert _shared_metric_keys(exps) == ["acc", "f1", "loss"]


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_requires_two_experiments(self, facade: DataFacade) -> None:
        with pytest.raises(ValueError):
            ComparisonScreen(facade=facade, experiments=[])


# ---------------------------------------------------------------------------
# Multi-selection on the experiments screen
# ---------------------------------------------------------------------------


class TestMultiSelection:
    async def test_space_toggles_selection(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment(
            tracker, name="alpha", static_params={"lr": 0.01}
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentsScreen(
                facade=facade, group_id=tracker.list_groups()[0].id,
                group_name="g",
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            await pilot.pause()
            assert not app.is_experiment_selected(exp_id)
            screen.action_toggle_selection()
            await pilot.pause()
            assert app.is_experiment_selected(exp_id)
            assert app.selected_experiment_ids == [exp_id]
            screen.action_toggle_selection()
            await pilot.pause()
            assert not app.is_experiment_selected(exp_id)
            assert app.selected_experiment_ids == []

    async def test_selection_persists_across_groups(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """Per SPEC: selected items survive navigation between groups."""

        g1 = tracker.create_group("g1")
        g2 = tracker.create_group("g2")
        exp_a = tracker.start_experiment(name="a", group=g1.name)
        exp_b = tracker.start_experiment(name="b", group=g2.name)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Open g1 and toggle exp_a.
            screen1 = ExperimentsScreen(
                facade=facade, group_id=g1.id, group_name=g1.name
            )
            app.push_screen(screen1)
            await pilot.pause()
            await pilot.pause()
            screen1.query_one("#experiments-table", DataTable).focus()
            await pilot.pause()
            screen1.action_toggle_selection()
            await pilot.pause()
            assert app.is_experiment_selected(exp_a)
            # Pop and open g2 — selection survives the navigation.
            app.pop_screen()
            await pilot.pause()
            screen2 = ExperimentsScreen(
                facade=facade, group_id=g2.id, group_name=g2.name
            )
            app.push_screen(screen2)
            await pilot.pause()
            await pilot.pause()
            screen2.query_one("#experiments-table", DataTable).focus()
            await pilot.pause()
            screen2.action_toggle_selection()
            await pilot.pause()
            assert app.is_experiment_selected(exp_a)
            assert app.is_experiment_selected(exp_b)

    async def test_compare_without_selection_shows_toast(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        """With only one selectable row, `c` cannot reach 2 — must warn."""

        tracker.create_group("g")
        tracker.start_experiment(name="solo", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentsScreen(
                facade=facade, group_id=tracker.list_groups()[0].id,
                group_name="g",
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            # `c` should auto-pick the focused row but with only one
            # experiment in the store the screen stays put with a toast.
            screen.action_compare_selected()
            await pilot.pause()
            assert isinstance(app.screen, ExperimentsScreen)

    async def test_compare_opens_with_selection(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        _seed_experiment(
            tracker, name="alpha", static_params={"lr": 0.01}
        )
        _seed_experiment(
            tracker, name="beta", static_params={"lr": 0.001}
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ExperimentsScreen(
                facade=facade, group_id=tracker.list_groups()[0].id,
                group_name="g",
            )
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            # Toggle both rows.
            screen.action_toggle_selection()
            table = screen.query_one("#experiments-table", DataTable)
            table.focus()
            table.move_cursor(row=1)
            await pilot.pause()
            screen.action_toggle_selection()
            await pilot.pause()
            assert len(app.selected_experiment_ids) == 2
            screen.action_compare_selected()
            await pilot.pause()
            await pilot.pause()
            assert isinstance(app.screen, ComparisonScreen)


# ---------------------------------------------------------------------------
# ComparisonScreen rendering
# ---------------------------------------------------------------------------


class TestStaticParamDiff:
    async def test_diff_rows_highlighted(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        ea = _seed_experiment(
            tracker,
            name="alpha",
            static_params={"lr": 0.01, "batch": 32},
        )
        eb = _seed_experiment(
            tracker,
            name="beta",
            static_params={"lr": 0.001, "batch": 32},
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#cmp-params-table", DataTable)
            # Two rows: batch (same), lr (diff). Order is sorted by key.
            keys = list(table.rows.keys())
            assert any(
                k.value == "cmp-param-lr" for k in keys
            ), f"expected lr row, got {[k.value for k in keys]}"
            assert any(
                k.value == "cmp-param-batch" for k in keys
            )
            # Inspect the diff style on the `lr` row's key cell.
            lr_cell = table.get_cell("cmp-param-lr", "cmp-param-key")
            assert "diff-changed" in str(lr_cell.style)

    async def test_no_static_params_renders_placeholder(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        ea = _seed_experiment(tracker, name="alpha")
        eb = _seed_experiment(tracker, name="beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#cmp-params-table", DataTable)
            keys = [k.value for k in table.rows.keys()]
            assert "cmp-empty" in keys


# ---------------------------------------------------------------------------
# Metric overlay
# ---------------------------------------------------------------------------


class TestMetricOverlay:
    async def test_metric_chooser_populated_with_union(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(
            tracker,
            name="alpha",
            metric_series={"loss": [(i, 1.0 / (i + 1)) for i in range(5)]},
        )
        eb = _seed_experiment(
            tracker,
            name="beta",
            metric_series={
                "loss": [(i, 0.5 / (i + 1)) for i in range(5)],
                "acc": [(i, 0.1 * i) for i in range(5)],
            },
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            assert set(screen._metric_keys) == {"loss", "acc"}
            # Both keys are surfaced in the ListView.
            view = screen.query_one("#cmp-metric-list", ListView)
            assert len(view.children) == 2

    async def test_first_metric_auto_selected(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(
            tracker,
            name="alpha",
            metric_series={"loss": [(i, 1.0 / (i + 1)) for i in range(5)]},
        )
        eb = _seed_experiment(
            tracker,
            name="beta",
            metric_series={"loss": [(i, 0.5 / (i + 1)) for i in range(5)]},
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            assert screen._selected_metric == "loss"

    async def test_overlay_loads_per_experiment_series(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(
            tracker,
            name="alpha",
            metric_series={"loss": [(i, 1.0 / (i + 1)) for i in range(8)]},
        )
        eb = _seed_experiment(
            tracker,
            name="beta",
            metric_series={"loss": [(i, 0.5 / (i + 1)) for i in range(8)]},
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            # Give the worker threads time to land their results. Both
            # fetches share the SQLite store, so under heavy test-suite
            # load the facade may end up serializing them — wait until
            # both have non-None histories rather than counting fixed
            # ticks. The bound is generous and quickly satisfied in the
            # common case.
            for _ in range(40):
                await pilot.pause()
                both_loaded = (
                    ea in screen._metric_histories
                    and eb in screen._metric_histories
                    and all(
                        screen._metric_histories[k] is not None
                        for k in (ea, eb)
                    )
                )
                if both_loaded:
                    break
            assert ea in screen._metric_histories
            assert eb in screen._metric_histories
            for history in screen._metric_histories.values():
                assert history is not None
                assert history.history  # at least one point per exp


# ---------------------------------------------------------------------------
# Eval score comparison
# ---------------------------------------------------------------------------


class TestEvalScoreCompare:
    async def test_score_rows_for_shared_dataset(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(
            tracker,
            name="alpha",
            evals=[
                (
                    "e-1",
                    "ds-1",
                    {"prompt": "hi"},
                    {"answer": "yo"},
                    {"expected": "yo"},
                    {"accuracy": 0.9},
                ),
            ],
        )
        eb = _seed_experiment(
            tracker,
            name="beta",
            evals=[
                (
                    "e-2",
                    "ds-1",
                    {"prompt": "hi"},
                    {"answer": "yo"},
                    {"expected": "yo"},
                    {"accuracy": 0.5},
                ),
            ],
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            # Let the eval-scores worker complete.
            for _ in range(20):
                await pilot.pause()
                if screen._eval_scores.get(ea) and screen._eval_scores.get(eb):
                    break
            table = screen.query_one("#cmp-evals-table", DataTable)
            row_keys = [k.value for k in table.rows.keys()]
            assert any(
                rk and "ds-1" in rk and "accuracy" in rk for rk in row_keys
            )

    async def test_handles_no_evals(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(tracker, name="alpha")
        eb = _seed_experiment(tracker, name="beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            # Drive a few cycles so the worker's "no datasets" path lands.
            for _ in range(10):
                await pilot.pause()
            table = screen.query_one("#cmp-evals-table", DataTable)
            row_keys = [k.value for k in table.rows.keys()]
            assert "cmp-evals-empty" in row_keys


# ---------------------------------------------------------------------------
# Breadcrumb
# ---------------------------------------------------------------------------


class TestBreadcrumb:
    async def test_breadcrumb_reflects_selection_count(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(tracker, name="alpha")
        eb = _seed_experiment(tracker, name="beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            segs = screen.breadcrumb_segments()
            labels = [s.label for s in segs]
            assert labels == ["Groups", "Compare (2)"]


# ---------------------------------------------------------------------------
# Panel-frame sections + colored legend
# ---------------------------------------------------------------------------


class TestComparisonPanelFrames:
    """Each section is wrapped in a titled ``PanelFrame``."""

    async def test_each_section_is_a_panel_frame(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(tracker, name="alpha", static_params={"lr": 0.01})
        eb = _seed_experiment(tracker, name="beta", static_params={"lr": 0.001})
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            sections = {
                "cmp-summary-card": "Comparing 2 experiments",
                "cmp-params-card": "Static parameters",
                "cmp-metric-card": "Metric overlay",
                "cmp-evals-card": "Eval scores",
            }
            for card_id, title in sections.items():
                frame = screen.query_one(f"#{card_id}", PanelFrame)
                assert frame.title == title
                assert frame.border_title == title


class TestComparisonLegend:
    """The legend maps each experiment name to its plotted color.

    Same color index drives the metric overlay series and the diff-table
    column header, so a single legend anchors the colors across all
    three sections. The legend renders inside the summary panel above
    the metric overlay.
    """

    async def test_legend_names_use_series_colors(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        ea = _seed_experiment(tracker, name="alpha")
        eb = _seed_experiment(tracker, name="beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            legend = screen.query_one("#cmp-legend", Static)
            rendered = str(legend.render())
            # Both experiment names are present, and the colors are the
            # same stable index used elsewhere (cyan / magenta etc.).
            assert "alpha" in rendered
            assert "beta" in rendered
            assert _rich_color_for(0) == "cyan"
            assert _rich_color_for(1) == "magenta"

    async def test_legend_lives_in_summary_card(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        """The legend renders inside the summary card so the colored
        names sit above the metric overlay rather than competing with
        the diff table for the user's attention."""

        ea = _seed_experiment(tracker, name="alpha")
        eb = _seed_experiment(tracker, name="beta")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            summary_card = screen.query_one("#cmp-summary-card", PanelFrame)
            legend = screen.query_one("#cmp-legend", Static)
            # The legend is a descendant of the summary panel.
            parent = legend.parent
            while parent is not None and parent is not summary_card:
                parent = parent.parent
            assert parent is summary_card

    async def test_diff_rows_still_highlighted_with_frames(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
    ) -> None:
        """Wrapping the sections in panel frames must not regress the
        diff-row coloring on the static-params table."""

        ea = _seed_experiment(
            tracker, name="alpha", static_params={"lr": 0.01}
        )
        eb = _seed_experiment(
            tracker, name="beta", static_params={"lr": 0.001}
        )
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
            screen = _push_comparison(app, facade, details)
            await pilot.pause()
            await pilot.pause()
            table = screen.query_one("#cmp-params-table", DataTable)
            lr_cell = table.get_cell("cmp-param-lr", "cmp-param-key")
            assert "diff-changed" in str(lr_cell.style)


class TestBodyScrolling:
    """j/k/g/G/ctrl+d/ctrl+u drive the scrollable comparison body."""

    async def test_body_is_scrollable_and_keys_move_it(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        from textual.containers import VerticalScroll

        ea = _seed_experiment(
            tracker,
            name="a",
            static_params={f"param_{i}": i for i in range(30)},
        )
        eb = _seed_experiment(
            tracker,
            name="b",
            static_params={f"param_{i}": i + 1 for i in range(30)},
        )
        details = [_fetch_details(facade, ea), _fetch_details(facade, eb)]
        app = _make_app(facade)
        # A short terminal so the stacked cards overflow the viewport.
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause()
            screen = _push_comparison(app, facade, details)
            for _ in range(5):
                await pilot.pause()
            body = screen.query_one("#cmp-body", VerticalScroll)
            assert body.scroll_y == 0
            screen.action_body_scroll_end()
            await pilot.pause()
            assert body.scroll_y > 0
            screen.action_body_scroll_home()
            await pilot.pause()
            assert body.scroll_y == 0
            screen.action_body_half_page_down()
            await pilot.pause()
            assert body.scroll_y > 0
            screen.action_body_half_page_up()
            await pilot.pause()
            assert body.scroll_y == 0
