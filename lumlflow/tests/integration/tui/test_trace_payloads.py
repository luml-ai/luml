"""Trace detail screen: span tree from the structure, span payloads on demand."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.schemas.experiments import Span
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade, Result
from lumlflow.tui.screens.trace_detail import (
    SPAN_LOAD_ERROR_TEXT,
    SPAN_LOADING_TEXT,
    SPAN_PAYLOAD_CACHE_SIZE,
    VALUE_PREVIEW_CHARS,
    TraceDetailScreen,
)
from textual.pilot import Pilot
from textual.widgets import Static, Tree

from tests.helpers.tui import settle_workers

TRACE_ID = "tr-payloads"


class RecordingFacade(DataFacade):
    def __init__(self, tracker: ExperimentTracker) -> None:
        super().__init__(tracker=tracker)
        self.span_reads: list[str] = []
        self.failing_spans: set[str] = set()
        self.blocked_spans: dict[str, threading.Event] = {}

    def get_span(self, experiment_id: str, trace_id: str, span_id: str) -> Result[Span]:
        self.span_reads.append(span_id)
        gate = self.blocked_spans.get(span_id)
        if gate is not None:
            gate.wait(timeout=10)
        if span_id in self.failing_spans:
            return Result.failure(500, "disk I/O error")
        return super().get_span(experiment_id, trace_id, span_id)


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> RecordingFacade:
    return RecordingFacade(tracker)


def _seed(tracker: ExperimentTracker, long_value: str = "short") -> str:
    tracker.create_group("g")
    exp_id = tracker.start_experiment(name="exp", group="g")
    spans: list[tuple[str, str | None, dict[str, Any]]] = [
        ("root", None, {"role": "root"}),
        ("child-a", "root", {"role": "child-a", "prompt": long_value}),
        ("child-b", "root", {"role": "child-b"}),
    ]
    for index, (span_id, parent, attributes) in enumerate(spans):
        tracker.log_span(
            trace_id=TRACE_ID,
            span_id=span_id,
            name=span_id,
            parent_span_id=parent,
            start_time_unix_nano=index * 1_000,
            end_time_unix_nano=10_000,
            attributes=attributes,
            events=[{"name": f"{span_id}-event", "timestamp": index * 1_000}],
            experiment_id=exp_id,
        )
    tracker.end_experiment(experiment_id=exp_id)
    return exp_id


async def _open(
    pilot: Pilot[Any], facade: DataFacade, exp_id: str
) -> TraceDetailScreen:
    screen = TraceDetailScreen(facade=facade, experiment_id=exp_id, trace_id=TRACE_ID)
    pilot.app.push_screen(screen)
    await settle_workers(pilot)
    return screen


def _attrs(screen: TraceDetailScreen) -> str:
    return str(screen.query_one("#span-detail-attrs", Static).render())


def _events(screen: TraceDetailScreen) -> str:
    return str(screen.query_one("#span-detail-events", Static).render())


async def test_tree_renders_from_the_structure(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)

        assert set(screen._tree_nodes) == {"root", "child-a", "child-b"}
        tree = screen.query_one("#span-tree", Tree)
        [root] = tree.root.children
        assert [child.data for child in root.children] == ["child-a", "child-b"]
        assert all(span.attributes is None for span in screen._spans_by_id.values())
        assert facade.span_reads == ["root"]
        assert "role = root" in _attrs(screen)
        assert "root-event" in _events(screen)


async def test_selection_reads_each_span_once(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        for span_id in ("child-a", "child-b", "child-a", "root"):
            screen._set_selected_span(span_id)
            await settle_workers(pilot)
            assert f"role = {span_id}" in _attrs(screen)

        assert facade.span_reads == ["root", "child-a", "child-b"]


async def test_loading_line_then_payload(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        gate = threading.Event()
        facade.blocked_spans["child-b"] = gate

        screen._set_selected_span("child-b")
        await pilot.pause()
        assert _attrs(screen) == SPAN_LOADING_TEXT
        assert "child-b" in str(
            screen.query_one("#span-detail-header", Static).render()
        )

        gate.set()
        await settle_workers(pilot)
        assert "role = child-b" in _attrs(screen)


async def test_a_stale_answer_is_cached_but_not_shown(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        gate = threading.Event()
        facade.blocked_spans["child-a"] = gate

        screen._set_selected_span("child-a")
        await pilot.pause()
        screen._set_selected_span("child-b")
        await pilot.pause()
        gate.set()
        await settle_workers(pilot)

        assert "role = child-b" in _attrs(screen)
        assert "child-a" in screen._span_payloads
        assert facade.span_reads == ["root", "child-a", "child-b"]


async def test_only_the_latest_queued_span_is_read(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        screen._span_payloads.clear()
        gate = threading.Event()
        facade.blocked_spans["child-a"] = gate

        screen._set_selected_span("child-a")
        await pilot.pause()
        screen._set_selected_span("child-b")
        screen._set_selected_span("root")
        gate.set()
        await settle_workers(pilot)

        assert facade.span_reads == ["root", "child-a", "root"]
        assert "role = root" in _attrs(screen)


async def test_long_value_is_shortened_until_show_all(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    long_value = "x" * 10_000 + "END"
    exp_id = _seed(tracker, long_value=long_value)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        screen._set_selected_span("child-a")
        await settle_workers(pilot)

        shortened = _attrs(screen)
        assert "x" * VALUE_PREVIEW_CHARS in shortened
        assert "x" * (VALUE_PREVIEW_CHARS + 1) not in shortened
        assert "END" not in shortened
        hint = "prompt = First 4,000 characters of 9.8 KiB. Press v to show all.\nxxx"
        assert hint in shortened
        assert "role = child-a" in shortened

        await pilot.press("v")
        await pilot.pause()
        assert long_value in _attrs(screen)
        assert "Press v" not in _attrs(screen)

        await pilot.press("v")
        await pilot.pause()
        assert "END" not in _attrs(screen)

        await pilot.press("v")
        screen._set_selected_span("child-b")
        screen._set_selected_span("child-a")
        await pilot.pause()
        assert "END" not in _attrs(screen)
        assert facade.span_reads == ["root", "child-a", "child-b"]


async def test_error_line_and_retry_on_next_selection(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    facade.failing_spans.add("child-a")
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        screen._set_selected_span("child-a")
        await settle_workers(pilot)

        assert _attrs(screen) == SPAN_LOAD_ERROR_TEXT
        assert _events(screen) == ""
        assert "child-a" not in screen._span_payloads

        facade.failing_spans.clear()
        screen._set_selected_span("child-b")
        screen._set_selected_span("child-a")
        await settle_workers(pilot)
        assert "role = child-a" in _attrs(screen)


async def test_payload_cache_is_bounded_and_keeps_recent_and_shown_spans(
    facade: RecordingFacade, tracker: ExperimentTracker
) -> None:
    exp_id = _seed(tracker)
    async with LumlflowApp(facade=facade).run_test() as pilot:
        screen = await _open(pilot, facade, exp_id)
        stand_in = screen._span_payloads["root"]
        for index in range(SPAN_PAYLOAD_CACHE_SIZE - 1):
            screen._remember_span_payload(f"old-{index}", stand_in)
        assert list(screen._span_payloads)[0] == "root"

        screen._set_selected_span("child-a")
        await settle_workers(pilot)
        assert len(screen._span_payloads) == SPAN_PAYLOAD_CACHE_SIZE
        assert "root" not in screen._span_payloads

        screen._set_selected_span("child-b")
        await settle_workers(pilot)
        screen._set_selected_span("child-a")
        await pilot.pause()
        assert list(screen._span_payloads)[-1] == "child-a"
        for index in range(SPAN_PAYLOAD_CACHE_SIZE):
            screen._remember_span_payload(f"new-{index}", stand_in)

        assert len(screen._span_payloads) == SPAN_PAYLOAD_CACHE_SIZE
        assert "child-a" in screen._span_payloads
        assert "child-b" not in screen._span_payloads
        assert "role = child-a" in _attrs(screen)
        assert facade.span_reads == ["root", "child-a", "child-b"]
