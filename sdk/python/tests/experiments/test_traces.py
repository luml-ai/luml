import pytest

from luml.experiments.backends.data_types import (
    PaginatedResponse,
    TraceDetails,
    TraceRecord,
    TraceState,
)
from luml.experiments.tracker import ExperimentTracker


class TestLogSpan:
    def test_persists_trace_and_span_ids(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="trace1",
            span_id="span1",
            name="preprocess",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )

        result = tracker.get_trace(exp_id, "trace1")

        assert result is not None
        assert result.trace_id == "trace1"
        assert result.spans[0].span_id == "span1"
        assert result.spans[0].name == "preprocess"

    def test_timing_fields_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        start = 1_000_000_000
        end = 3_000_000_000
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=start,
            end_time_unix_nano=end,
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        span = result.spans[0]
        assert span.start_time_unix_nano == start
        assert span.end_time_unix_nano == end

    def test_optional_fields_default_to_none(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        span = result.spans[0]
        assert span.parent_span_id is None
        assert span.status_message is None
        assert span.attributes is None
        assert span.events is None
        assert span.links is None

    def test_span_attributes_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            attributes={"rows": 1000, "source": "csv"},
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        assert result.spans[0].attributes == {"rows": 1000, "source": "csv"}

    def test_span_events_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        events = [{"name": "cache_miss", "timestamp": 1_000_000}]
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            events=events,
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        assert result.spans[0].events == events

    def test_span_links_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        links = [{"trace_id": "other", "span_id": "s0"}]
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            links=links,
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        assert result.spans[0].links == links

    def test_parent_span_id_stored(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="root",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )
        tracker.log_span(
            trace_id="t1",
            span_id="child",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            parent_span_id="root",
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        by_id = {s.span_id: s for s in result.spans}
        assert by_id["child"].parent_span_id == "root"
        assert by_id["root"].parent_span_id is None

    def test_status_fields_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            status_code=2,
            status_message="timeout",
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        span = result.spans[0]
        assert span.status_code == 2
        assert span.status_message == "timeout"

    def test_kind_and_trace_flags_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            kind=2,
            trace_flags=1,
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        span = result.spans[0]
        assert span.kind == 2
        assert span.trace_flags == 1

    def test_multiple_spans_same_trace(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        for i in range(3):
            tracker.log_span(
                trace_id="multi",
                span_id=f"s{i}",
                name=f"step_{i}",
                start_time_unix_nano=1_000_000_000,
                end_time_unix_nano=2_000_000_000,
            )

        result = tracker.get_trace(exp_id, "multi")

        assert result is not None
        assert len(result.spans) == 3

    def test_explicit_experiment_id(
        self,
        tracker: ExperimentTracker,
    ) -> None:
        exp_id = tracker.start_experiment(name="exp_a")
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            experiment_id=exp_id,
        )

        result = tracker.get_trace(exp_id, "t1")

        assert result is not None
        assert len(result.spans) == 1

    def test_requires_active_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_span(
                trace_id="t",
                span_id="s",
                name="op",
                start_time_unix_nano=0,
                end_time_unix_nano=1,
            )


class TestGetTrace:
    def test_returns_trace_details(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t_get",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )

        result = tracker.get_trace(exp_id, "t_get")

        assert result is not None
        assert isinstance(result, TraceDetails)
        assert result.trace_id == "t_get"

    def test_returns_all_spans_for_trace(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        for i in range(3):
            tracker.log_span(
                trace_id="t_multi",
                span_id=f"s{i}",
                name="op",
                start_time_unix_nano=now + i * 1000,
                end_time_unix_nano=now + i * 1000 + 500,
            )

        result = tracker.get_trace(exp_id, "t_multi")

        assert result is not None
        assert len(result.spans) == 3

    def test_span_fields_populated(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t_fields",
            span_id="s1",
            name="my_op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
            attributes={"key": "val"},
        )

        result = tracker.get_trace(exp_id, "t_fields")

        assert result is not None
        span = result.spans[0]
        assert span.span_id == "s1"
        assert span.trace_id == "t_fields"
        assert span.name == "my_op"
        assert span.start_time_unix_nano == 1_000_000_000
        assert span.end_time_unix_nano == 2_000_000_000
        assert span.attributes == {"key": "val"}

    def test_returns_none_for_missing_trace(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.get_trace(exp_id, "nonexistent")

        assert result is None

    def test_does_not_return_spans_from_other_traces(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="trace_a",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )
        tracker.log_span(
            trace_id="trace_b",
            span_id="s2",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )

        result = tracker.get_trace(exp_id, "trace_a")

        assert result is not None
        assert len(result.spans) == 1
        assert result.spans[0].span_id == "s1"

    def test_parent_child_hierarchy_preserved(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        tracker.log_span(
            trace_id="t_tree",
            span_id="root",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1000,
        )
        tracker.log_span(
            trace_id="t_tree",
            span_id="child",
            name="op",
            start_time_unix_nano=now + 100,
            end_time_unix_nano=now + 500,
            parent_span_id="root",
        )

        result = tracker.get_trace(exp_id, "t_tree")

        assert result is not None
        by_id = {s.span_id: s for s in result.spans}
        assert by_id["child"].parent_span_id == "root"
        assert by_id["root"].parent_span_id is None


class TestGetExperimentTraces:
    def test_returns_paginated_response(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )

        result = tracker.get_experiment_traces(exp_id)

        assert isinstance(result, PaginatedResponse)
        assert len(result.items) == 1
        assert isinstance(result.items[0], TraceRecord)

    def test_each_trace_record_has_correct_trace_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="trace_abc",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000_000,
            end_time_unix_nano=2_000_000_000,
        )

        result = tracker.get_experiment_traces(exp_id)

        assert result.items[0].trace_id == "trace_abc"

    def test_span_count_reflects_number_of_spans(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        for i in range(4):
            tracker.log_span(
                trace_id="t_count",
                span_id=f"s{i}",
                name="op",
                start_time_unix_nano=now + i,
                end_time_unix_nano=now + i + 1,
            )

        result = tracker.get_experiment_traces(exp_id)

        assert result.items[0].span_count == 4

    def test_limit_restricts_page_size(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        for i in range(5):
            tracker.log_span(
                trace_id=f"t{i}",
                span_id="s1",
                name="op",
                start_time_unix_nano=now + i * 100,
                end_time_unix_nano=now + i * 100 + 50,
            )

        result = tracker.get_experiment_traces(exp_id, limit=3)

        assert len(result.items) == 3

    def test_cursor_pagination_covers_all_traces(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        for i in range(4):
            tracker.log_span(
                trace_id=f"tc{i}",
                span_id="s1",
                name="op",
                start_time_unix_nano=now + i * 100,
                end_time_unix_nano=now + i * 100 + 50,
            )

        page1 = tracker.get_experiment_traces(exp_id, limit=2, order="asc")
        assert page1.cursor is not None

        page2 = tracker.get_experiment_traces(
            exp_id, limit=2, order="asc", cursor_str=page1.cursor
        )

        ids1 = {r.trace_id for r in page1.items}
        ids2 = {r.trace_id for r in page2.items}
        assert ids1.isdisjoint(ids2)
        assert len(ids1 | ids2) == 4

    def test_search_filters_by_trace_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        tracker.log_span(
            trace_id="alpha_trace",
            span_id="s1",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1,
        )
        tracker.log_span(
            trace_id="beta_trace",
            span_id="s1",
            name="op",
            start_time_unix_nano=now + 2,
            end_time_unix_nano=now + 3,
        )

        result = tracker.get_experiment_traces(exp_id, search="alpha")

        assert len(result.items) == 1
        assert result.items[0].trace_id == "alpha_trace"

    def test_filter_by_state(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        tracker.log_span(
            trace_id="t_ok",
            span_id="s1",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1_000_000_000,
            status_code=1,
        )
        # Log only a child span (no root span) → state becomes IN_PROGRESS
        tracker.log_span(
            trace_id="t_inprogress",
            span_id="s1",
            name="op",
            parent_span_id="some-parent",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1_000_000_000,
        )

        all_traces = tracker.get_experiment_traces(exp_id)
        assert len(all_traces.items) == 2
        assert {t.trace_id for t in all_traces.items} == {"t_ok", "t_inprogress"}

        ok_traces = tracker.get_experiment_traces(exp_id, states=[TraceState.OK])
        assert len(ok_traces.items) == 1
        assert ok_traces.items[0].trace_id == "t_ok"

        in_progress_traces = tracker.get_experiment_traces(
            exp_id, states=[TraceState.IN_PROGRESS]
        )
        assert len(in_progress_traces.items) == 1
        assert in_progress_traces.items[0].trace_id == "t_inprogress"

    def test_empty_experiment_returns_empty_page(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.get_experiment_traces(exp_id)

        assert result.items == []
        assert result.cursor is None

    def test_pagination_covers_all_traces_without_duplicates(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        num = 25

        for i in range(num):
            tracker.log_span(
                trace_id=f"trace-{i:03d}",
                span_id=f"span-{i}",
                name=f"op-{i}",
                start_time_unix_nano=1_000_000_000 * i,
                end_time_unix_nano=1_000_000_000 * i + 500_000_000,
            )

        collected = []
        cursor = None
        while True:
            page = tracker.get_experiment_traces(exp_id, limit=10, cursor_str=cursor)
            collected.extend(page.items)
            if page.cursor is None:
                break
            cursor = page.cursor

        assert len(collected) == num
        assert len({t.trace_id for t in collected}) == num

    def test_multi_span_trace_reports_correct_span_count(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        # root → child-a, child-b → grandchild
        tracker.log_span(
            trace_id="t1",
            span_id="root",
            name="pipeline",
            start_time_unix_nano=0,
            end_time_unix_nano=4_000_000_000,
        )
        tracker.log_span(
            trace_id="t1",
            span_id="child-a",
            name="preprocess",
            start_time_unix_nano=100_000_000,
            end_time_unix_nano=1_500_000_000,
            parent_span_id="root",
        )
        tracker.log_span(
            trace_id="t1",
            span_id="child-b",
            name="inference",
            start_time_unix_nano=1_600_000_000,
            end_time_unix_nano=3_800_000_000,
            parent_span_id="root",
        )
        tracker.log_span(
            trace_id="t1",
            span_id="grandchild",
            name="postprocess",
            start_time_unix_nano=3_000_000_000,
            end_time_unix_nano=3_700_000_000,
            parent_span_id="child-b",
        )

        traces = tracker.get_experiment_traces_all(exp_id)
        assert len(traces) == 1

        detail = tracker.get_trace(exp_id, "t1")
        assert detail is not None
        assert len(detail.spans) == 4


class TestGetExperimentTracesAll:
    def test_all_traces_retrievable_without_pagination(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        num = 30

        for i in range(num):
            tracker.log_span(
                trace_id=f"trace-{i:03d}",
                span_id=f"span-{i}",
                name=f"op-{i}",
                start_time_unix_nano=1_000_000_000 * i,
                end_time_unix_nano=1_000_000_000 * i + 500_000_000,
            )

        traces = tracker.get_experiment_traces_all(exp_id)
        assert len(traces) == num

    def test_search_filters_by_trace_id_substring(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        tracker.log_span(
            trace_id="train_001",
            span_id="s1",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1,
        )
        tracker.log_span(
            trace_id="test_001",
            span_id="s1",
            name="op",
            start_time_unix_nano=now + 2,
            end_time_unix_nano=now + 3,
        )
        tracker.log_span(
            trace_id="train_002",
            span_id="s1",
            name="op",
            start_time_unix_nano=now + 4,
            end_time_unix_nano=now + 5,
        )

        result = tracker.get_experiment_traces_all(exp_id, search="train")

        assert len(result) == 2
        assert all("train" in r.trace_id for r in result)

    def test_empty_experiment_returns_empty_list(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.get_experiment_traces_all(exp_id)

        assert result == []

    def test_multiple_spans_same_trace_counted_as_one(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        for i in range(3):
            tracker.log_span(
                trace_id="single_trace",
                span_id=f"s{i}",
                name="op",
                start_time_unix_nano=now + i,
                end_time_unix_nano=now + i + 1,
            )

        result = tracker.get_experiment_traces_all(exp_id)

        assert len(result) == 1
        assert result[0].trace_id == "single_trace"
        assert result[0].span_count == 3

    def test_state_filter_in_progress(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        now = 1_000_000_000
        tracker.log_span(
            trace_id="t_done",
            span_id="s1",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now + 1_000_000_000,
        )
        tracker.log_span(
            trace_id="t_inprog",
            span_id="s1",
            name="op",
            start_time_unix_nano=now,
            end_time_unix_nano=now,
        )

        result = tracker.get_experiment_traces_all(
            exp_id, states=[TraceState.IN_PROGRESS]
        )

        assert all(r.state == TraceState.IN_PROGRESS for r in result)
