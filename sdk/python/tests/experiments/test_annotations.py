import sqlite3
from pathlib import Path

import pytest

from luml.experiments.backends.data_types import (
    AnnotationKind,
    AnnotationRecord,
    AnnotationSummary,
    AnnotationValueType,
    ExpectationSummaryItem,
    FeedbackSummaryItem,
)
from luml.experiments.backends.sqlite import SQLiteBackend
from luml.experiments.tracker import ExperimentTracker


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def tracker_with_experiment(
    tracker: ExperimentTracker,
) -> tuple[ExperimentTracker, str]:
    exp_id = tracker.start_experiment(name="test_exp")
    return tracker, exp_id


@pytest.fixture
def backend_with_experiment(
    tmp_path: Path,
) -> tuple[SQLiteBackend, str]:
    backend = SQLiteBackend(str(tmp_path / "experiments"))
    exp_id = "test-exp-id"
    backend.initialize_experiment(exp_id, "default", "test")
    return backend, exp_id


def _seed_eval(backend: SQLiteBackend, experiment_id: str) -> tuple[str, str]:
    dataset_id = "ds-1"
    eval_id = "eval-1"
    backend.log_eval_sample(
        experiment_id,
        eval_id,
        dataset_id,
        inputs={"prompt": "hello"},
    )
    return dataset_id, eval_id


def seed_span_annotations(
    backend: SQLiteBackend, experiment_id: str
) -> tuple[str, str]:
    trace_id = "trace-1"
    span_id = "span-1"
    backend.log_span(
        experiment_id,
        trace_id,
        span_id,
        name="test-span",
        start_time_unix_nano=0,
        end_time_unix_nano=1000,
    )
    return trace_id, span_id


class TestEvalAnnotations:
    def test_log_feedback_bool(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )

        assert isinstance(record, AnnotationRecord)
        assert record.name == "accuracy"
        assert record.annotation_kind == AnnotationKind.FEEDBACK
        assert record.value_type == AnnotationValueType.BOOL
        assert record.value is True
        assert record.user == "alice"
        assert record.rationale is None
        assert record.id

    def test_log_with_rationale(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
            rationale="The answer is correct",
        )
        assert record.rationale == "The answer is correct"

        results = backend.get_eval_annotations(exp_id, dataset_id, eval_id)
        assert results[0].rationale == "The answer is correct"

    def test_log_expectation_string(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "quality",
            AnnotationKind.EXPECTATION,
            AnnotationValueType.STRING,
            "expected output",
            "bob",
        )

        assert record.annotation_kind == AnnotationKind.EXPECTATION
        assert record.value_type == AnnotationValueType.STRING
        assert record.value == "expected output"

    def test_get_eval_annotations_returns_multiple(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "quality",
            AnnotationKind.EXPECTATION,
            AnnotationValueType.STRING,
            "hello",
            "bob",
        )

        results = backend.get_eval_annotations(exp_id, dataset_id, eval_id)
        assert len(results) == 2
        assert results[0].annotation_kind == AnnotationKind.FEEDBACK
        assert results[1].annotation_kind == AnnotationKind.EXPECTATION

    def test_feedback_non_bool_raises(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        with pytest.raises(ValueError, match="value_type='bool'"):
            backend.log_eval_annotation(
                exp_id,
                dataset_id,
                eval_id,
                "accuracy",
                AnnotationKind.FEEDBACK,
                AnnotationValueType.STRING,
                "oops",
                "alice",
            )

    def test_bool_round_trip(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        for val in (True, False):
            record = backend.log_eval_annotation(
                exp_id,
                dataset_id,
                eval_id,
                "accuracy",
                AnnotationKind.FEEDBACK,
                AnnotationValueType.BOOL,
                val,
                "alice",
            )
            assert record.value is val

    def test_int_round_trip(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "score",
            AnnotationKind.EXPECTATION,
            AnnotationValueType.INT,
            42,
            "alice",
        )
        assert record.value == 42
        assert isinstance(record.value, int)

    def test_delete_annotation(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        backend.delete_annotation(exp_id, record.id, "eval")

        results = backend.get_eval_annotations(exp_id, dataset_id, eval_id)
        assert len(results) == 0

    def test_update_eval_annotation(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        updated = backend.update_annotation(
            exp_id,
            record.id,
            "eval",
            value=False,
            rationale="Changed my mind",
        )
        assert updated.value is False
        assert updated.rationale == "Changed my mind"

    def test_update_annotation_rationale_only(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        updated = backend.update_annotation(
            exp_id,
            record.id,
            "eval",
            rationale="Added rationale",
        )
        assert updated.value is True
        assert updated.rationale == "Added rationale"

    def test_update_annotation_no_fields_raises(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)

        record = backend.log_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            "accuracy",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        with pytest.raises(ValueError, match="No fields to update"):
            backend.update_annotation(exp_id, record.id, "eval")


class TestSpanAnnotations:
    def test_log_and_get_span_annotation(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        record = backend.log_span_annotation(
            exp_id,
            trace_id,
            span_id,
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            False,
            "carol",
        )
        assert record.value is False
        assert record.rationale is None

        results = backend.get_span_annotations(exp_id, trace_id, span_id)
        assert len(results) == 1
        assert results[0].id == record.id

    def test_log_span_annotation_with_rationale(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        record = backend.log_span_annotation(
            exp_id,
            trace_id,
            span_id,
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
            rationale="Span output was accurate",
        )
        assert record.rationale == "Span output was accurate"

        results = backend.get_span_annotations(exp_id, trace_id, span_id)
        assert results[0].rationale == "Span output was accurate"

    def test_update_span_annotation(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        record = backend.log_span_annotation(
            exp_id,
            trace_id,
            span_id,
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        updated = backend.update_annotation(
            exp_id,
            record.id,
            "span",
            rationale="Updated rationale",
        )
        assert updated.rationale == "Updated rationale"
        assert updated.value is True

    def test_delete_span_annotation(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        record = backend.log_span_annotation(
            exp_id,
            trace_id,
            span_id,
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "dave",
        )
        backend.delete_annotation(exp_id, record.id, "span")

        results = backend.get_span_annotations(exp_id, trace_id, span_id)
        assert len(results) == 0

    def test_annotation_count_in_get_trace(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        result = backend.get_trace(exp_id, trace_id)
        assert result is not None
        assert result.spans[0].annotation_count == 0

        backend.log_span_annotation(
            exp_id,
            trace_id,
            span_id,
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )

        result = backend.get_trace(exp_id, trace_id)
        assert result is not None
        assert result.spans[0].annotation_count == 1


class TestBackwardCompat:
    def test_annotations_on_db_without_tables(self, tmp_path: Path) -> None:
        """Old DBs (user_version=0) return empty annotations instead of failing."""
        backend = SQLiteBackend(str(tmp_path / "experiments"))
        exp_id = "old-exp"
        backend.initialize_experiment(exp_id, "default", "test")

        # Set user_version=0 and remove annotation tables to simulate an old DB
        db_path = tmp_path / "experiments" / exp_id / "exp.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS eval_annotations")
        conn.execute("DROP TABLE IF EXISTS span_annotations")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()

        # Close cached connection so it reconnects
        backend.pool.close_connection(str(db_path))

        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        assert backend.get_eval_annotations(exp_id, dataset_id, eval_id) == []
        assert backend.get_span_annotations(exp_id, trace_id, span_id) == []

        eval_summary = backend.get_eval_annotation_summary(exp_id, dataset_id)
        assert isinstance(eval_summary, AnnotationSummary)
        assert eval_summary.feedback == []
        assert eval_summary.expectations == []

        trace_summary = backend.get_trace_annotation_summary(exp_id, trace_id)
        assert isinstance(trace_summary, AnnotationSummary)
        assert trace_summary.feedback == []
        assert trace_summary.expectations == []

        result = backend.get_trace(exp_id, trace_id)
        assert result is not None
        assert result.spans[0].annotation_count == 0

    def test_write_raises_on_old_db(self, tmp_path: Path) -> None:
        """Writing annotations on an old DB raises ValueError."""
        backend = SQLiteBackend(str(tmp_path / "experiments"))
        exp_id = "old-exp"
        backend.initialize_experiment(exp_id, "default", "test")

        db_path = tmp_path / "experiments" / exp_id / "exp.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS eval_annotations")
        conn.execute("DROP TABLE IF EXISTS span_annotations")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()

        backend.pool.close_connection(str(db_path))

        dataset_id, eval_id = seed_eval_annotations(backend, exp_id)
        trace_id, span_id = seed_span_annotations(backend, exp_id)

        with pytest.raises(ValueError, match="older schema"):
            backend.log_eval_annotation(
                exp_id,
                dataset_id,
                eval_id,
                "quality",
                AnnotationKind.FEEDBACK,
                AnnotationValueType.BOOL,
                True,
                "alice",
            )

        with pytest.raises(ValueError, match="older schema"):
            backend.log_span_annotation(
                exp_id,
                trace_id,
                span_id,
                "latency",
                AnnotationKind.EXPECTATION,
                AnnotationValueType.INT,
                42,
                "bob",
            )


class TestTrackerAnnotations:
    def test_log_eval_annotation_via_tracker(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="eval-1",
            dataset_id="ds-1",
            inputs={"prompt": "hello"},
        )

        record = tracker.log_eval_annotation(
            dataset_id="ds-1",
            eval_id="eval-1",
            name="accuracy",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )

        assert isinstance(record, AnnotationRecord)
        assert record.name == "accuracy"
        assert record.value is True

    def test_log_span_annotation_via_tracker(
        self, tracker_with_experiment: tuple[ExperimentTracker, str]
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="trace-1",
            span_id="span-1",
            name="test",
            start_time_unix_nano=0,
            end_time_unix_nano=1000,
        )

        record = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="latency",
            annotation_kind="expectation",
            value_type="int",
            value=42,
            user="bob",
        )

        assert record.name == "latency"
        assert record.value == 42

    def test_tracker_no_experiment_raises(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_eval_annotation(
                dataset_id="ds-1",
                eval_id="eval-1",
                name="accuracy",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="alice",
            )


class TestAllTracesAnnotationSummary:
    def test_aggregates_across_traces(
        self, backend_with_experiment: tuple[SQLiteBackend, str]
    ) -> None:
        backend, exp_id = backend_with_experiment

        backend.log_span(
            exp_id,
            "trace-1",
            "span-1",
            name="s1",
            start_time_unix_nano=0,
            end_time_unix_nano=1000,
        )
        backend.log_span(
            exp_id,
            "trace-2",
            "span-2",
            name="s2",
            start_time_unix_nano=0,
            end_time_unix_nano=1000,
        )

        backend.log_span_annotation(
            exp_id,
            "trace-1",
            "span-1",
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            True,
            "alice",
        )
        backend.log_span_annotation(
            exp_id,
            "trace-2",
            "span-2",
            "quality",
            AnnotationKind.FEEDBACK,
            AnnotationValueType.BOOL,
            False,
            "bob",
        )

        summary = backend.get_all_traces_annotation_summary(exp_id)
        assert len(summary.feedback) == 1
        assert summary.feedback[0].name == "quality"
        assert summary.feedback[0].total == 2
        assert summary.feedback[0].counts == {"true": 1, "false": 1}

    def test_empty_on_old_db(self, tmp_path: Path) -> None:
        backend = SQLiteBackend(str(tmp_path / "experiments"))
        exp_id = "old-exp"
        backend.initialize_experiment(exp_id, "default", "test")

        db_path = tmp_path / "experiments" / exp_id / "exp.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS span_annotations")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        backend.pool.close_connection(str(db_path))

        summary = backend.get_all_traces_annotation_summary(exp_id)
        assert summary.feedback == []
        assert summary.expectations == []


class TestAnnotationSummary:
    def test_eval_feedback_summary_counts_match_logged_values(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        correctness = [True, True, False, True, False]
        for i, is_correct in enumerate(correctness):
            tracker.log_eval_sample(
                eval_id=f"eval-{i}",
                dataset_id="qa",
                inputs={"question": f"What is {i}*{i}?"},
                outputs={"answer": str(i * i)},
            )
            tracker.log_eval_annotation(
                dataset_id="qa",
                eval_id=f"eval-{i}",
                name="correct",
                annotation_kind="feedback",
                value_type="bool",
                value=is_correct,
                user="reviewer",
            )

        summary = tracker.get_eval_annotation_summary(exp_id, "qa")

        fb = next(f for f in summary.feedback if f.name == "correct")
        assert fb.total == 5
        assert fb.counts["true"] == 3
        assert fb.counts["false"] == 2

    def test_span_expectation_summary_covers_all_spans(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        scores = [3, 5, 4, 2]
        for i, score in enumerate(scores):
            tracker.log_span(
                trace_id="pipeline-run",
                span_id=f"step-{i}",
                name=f"stage-{i}",
                start_time_unix_nano=1_000_000_000 * i,
                end_time_unix_nano=1_000_000_000 * i + 800_000_000,
            )
            tracker.log_span_annotation(
                trace_id="pipeline-run",
                span_id=f"step-{i}",
                name="quality",
                annotation_kind="expectation",
                value_type="int",
                value=score,
                user="analyst",
            )

        summary = tracker.get_trace_annotation_summary(exp_id, "pipeline-run")

        exp = next(e for e in summary.expectations if e.name == "quality")
        assert exp.total == 4

    def test_multiple_annotators_all_appear_in_summary(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds",
            inputs={"prompt": "Translate to French: hello"},
            outputs={"text": "bonjour"},
        )
        for user, value in [("alice", True), ("bob", True), ("carol", False)]:
            tracker.log_eval_annotation(
                dataset_id="ds",
                eval_id="e1",
                name="fluent",
                annotation_kind="feedback",
                value_type="bool",
                value=value,
                user=user,
            )

        summary = tracker.get_eval_annotation_summary(exp_id, "ds")

        fb = next(f for f in summary.feedback if f.name == "fluent")
        assert fb.total == 3
        assert fb.counts["true"] == 2
        assert fb.counts["false"] == 1

    def test_feedback_and_expectation_coexist_on_same_eval(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds",
            inputs={"prompt": "Summarize the article."},
            outputs={"summary": "Short summary."},
        )
        tracker.log_eval_annotation(
            dataset_id="ds",
            eval_id="e1",
            name="correct",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        tracker.log_eval_annotation(
            dataset_id="ds",
            eval_id="e1",
            name="expected_length",
            annotation_kind="expectation",
            value_type="int",
            value=50,
            user="alice",
        )

        annotations = tracker.get_eval_annotations(exp_id, "ds", "e1")

        assert len(annotations) == 2
        by_name = {a.name: a for a in annotations}
        assert by_name["correct"].annotation_kind == "feedback"
        assert by_name["expected_length"].annotation_kind == "expectation"
        assert by_name["expected_length"].value == 50


class TestGetAllTracesAnnotationSummary:
    def _log_span(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        trace_id: str = "trace-1",
        span_id: str = "span-1",
    ) -> None:
        tracker.log_span(
            trace_id=trace_id,
            span_id=span_id,
            name="op",
            start_time_unix_nano=1_000_000,
            end_time_unix_nano=2_000_000,
            experiment_id=exp_id,
        )

    def _annotate(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        name: str,
        kind: str,
        value_type: str,
        value: int | bool | str,
        user: str = "alice",
        trace_id: str = "trace-1",
        span_id: str = "span-1",
    ) -> None:
        tracker.log_span_annotation(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            annotation_kind=kind,
            value_type=value_type,
            value=value,
            user=user,
            experiment_id=exp_id,
        )

    def test_returns_empty_when_no_annotation_tables(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "_has_annotation_tables", lambda _: False)

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        assert isinstance(summary, AnnotationSummary)
        assert summary.feedback == []
        assert summary.expectations == []

    def test_returns_empty_when_no_annotations_logged(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        assert summary.feedback == []
        assert summary.expectations == []

    def test_aggregates_feedback_counts_by_value(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)
        for _ in range(2):
            self._annotate(tracker, exp_id, "quality", "feedback", "bool", True)
        self._annotate(
            tracker, exp_id, "quality", "feedback", "bool", False, user="bob"
        )

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        assert len(summary.feedback) == 1
        fb = summary.feedback[0]
        assert isinstance(fb, FeedbackSummaryItem)
        assert fb.name == "quality"
        assert fb.total == 3
        assert fb.counts["true"] == 2
        assert fb.counts["false"] == 1

    def test_aggregates_multiple_feedback_names(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)
        self._annotate(tracker, exp_id, "quality", "feedback", "bool", True)
        self._annotate(tracker, exp_id, "relevance", "feedback", "bool", False)

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        names = {fb.name for fb in summary.feedback}
        assert names == {"quality", "relevance"}

    def test_aggregates_expectation_bool_positive_negative(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)
        self._annotate(tracker, exp_id, "passes_check", "expectation", "bool", True)
        self._annotate(
            tracker, exp_id, "passes_check", "expectation", "bool", True, user="bob"
        )
        self._annotate(
            tracker,
            exp_id,
            "passes_check",
            "expectation",
            "bool",
            False,
            user="charlie",
        )

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        assert len(summary.expectations) == 1
        exp_item = summary.expectations[0]
        assert isinstance(exp_item, ExpectationSummaryItem)
        assert exp_item.name == "passes_check"
        assert exp_item.total == 3
        assert exp_item.positive == 2
        assert exp_item.negative == 1

    def test_aggregates_expectation_non_bool_value(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)
        self._annotate(tracker, exp_id, "score", "expectation", "int", 42)

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        assert len(summary.expectations) == 1
        assert summary.expectations[0].value == 42

    def test_aggregates_annotations_across_multiple_traces(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, trace_id="trace-1", span_id="s1")
        self._log_span(tracker, exp_id, trace_id="trace-2", span_id="s2")
        self._annotate(
            tracker,
            exp_id,
            "quality",
            "feedback",
            "bool",
            True,
            trace_id="trace-1",
            span_id="s1",
        )
        self._annotate(
            tracker,
            exp_id,
            "quality",
            "feedback",
            "bool",
            True,
            trace_id="trace-2",
            span_id="s2",
        )

        summary = tracker.get_all_traces_annotation_summary(exp_id)

        assert len(summary.feedback) == 1
        assert summary.feedback[0].total == 2


class TestGetTracesAnnotationSummaries:
    def _log_span(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        trace_id: str,
        span_id: str,
    ) -> None:
        tracker.log_span(
            trace_id=trace_id,
            span_id=span_id,
            name="op",
            start_time_unix_nano=1_000_000,
            end_time_unix_nano=2_000_000,
            experiment_id=exp_id,
        )

    def _annotate(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        name: str,
        kind: str,
        value_type: str,
        value: int | bool | str,
        trace_id: str,
        span_id: str,
        user: str = "alice",
    ) -> None:
        tracker.log_span_annotation(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            annotation_kind=kind,
            value_type=value_type,
            value=value,
            user=user,
            experiment_id=exp_id,
        )

    def test_returns_empty_when_no_annotation_tables(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "_has_annotation_tables", lambda _: False)

        result = tracker.get_traces_annotation_summaries(exp_id, ["trace-1"])

        assert result == {}

    def test_returns_empty_for_empty_trace_ids(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        result = tracker.get_traces_annotation_summaries(exp_id, [])

        assert result == {}

    def test_returns_summary_per_trace_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._log_span(tracker, exp_id, "t2", "s2")
        self._annotate(tracker, exp_id, "quality", "feedback", "bool", True, "t1", "s1")
        self._annotate(
            tracker, exp_id, "quality", "feedback", "bool", False, "t2", "s2"
        )

        result = tracker.get_traces_annotation_summaries(exp_id, ["t1", "t2"])

        assert set(result.keys()) == {"t1", "t2"}
        assert isinstance(result["t1"], AnnotationSummary)
        assert isinstance(result["t2"], AnnotationSummary)

    def test_summaries_scoped_to_each_trace(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._log_span(tracker, exp_id, "t2", "s2")
        self._annotate(tracker, exp_id, "quality", "feedback", "bool", True, "t1", "s1")
        self._annotate(
            tracker, exp_id, "quality", "feedback", "bool", False, "t2", "s2"
        )

        result = tracker.get_traces_annotation_summaries(exp_id, ["t1", "t2"])

        assert result["t1"].feedback[0].counts == {"true": 1}
        assert result["t2"].feedback[0].counts == {"false": 1}

    def test_trace_without_annotations_excluded(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._log_span(tracker, exp_id, "t2", "s2")
        self._annotate(tracker, exp_id, "quality", "feedback", "bool", True, "t1", "s1")

        result = tracker.get_traces_annotation_summaries(exp_id, ["t1", "t2"])

        assert "t1" in result
        assert "t2" not in result

    def test_trace_with_both_feedback_and_expectation(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._annotate(tracker, exp_id, "quality", "feedback", "bool", True, "t1", "s1")
        self._annotate(
            tracker, exp_id, "passes", "expectation", "bool", True, "t1", "s1"
        )

        result = tracker.get_traces_annotation_summaries(exp_id, ["t1"])

        summary = result["t1"]
        assert len(summary.feedback) == 1
        assert len(summary.expectations) == 1
        assert summary.feedback[0].name == "quality"
        assert summary.expectations[0].name == "passes"


class TestDeleteAnnotation:
    def test_no_op_when_no_annotation_tables(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "_has_annotation_tables", lambda _: False)

        tracker.delete_annotation(exp_id, "any-id", "span")

    def test_deletes_span_annotation(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_span(
            trace_id="t1",
            span_id="s1",
            name="op",
            start_time_unix_nano=1_000_000,
            end_time_unix_nano=2_000_000,
            experiment_id=exp_id,
        )
        ann = tracker.log_span_annotation(
            trace_id="t1",
            span_id="s1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

        tracker.delete_annotation(exp_id, ann.id, "span")

        summary = tracker.get_all_traces_annotation_summary(exp_id)
        assert summary.feedback == []

    def test_deletes_eval_annotation(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"q": "hello"},
            experiment_id=exp_id,
        )
        ann = tracker.log_eval_annotation(
            dataset_id="ds1",
            eval_id="e1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

        tracker.delete_annotation(exp_id, ann.id, "eval")

        summary = tracker.get_eval_annotation_summary(exp_id, "ds1")
        assert summary.feedback == []

    def test_does_not_raise_for_nonexistent_annotation_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        tracker.delete_annotation(exp_id, "nonexistent-id", "span")

    def test_span_target_does_not_delete_eval_annotation(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        tracker.log_eval_sample(
            eval_id="e1",
            dataset_id="ds1",
            inputs={"q": "hi"},
            experiment_id=exp_id,
        )
        ann = tracker.log_eval_annotation(
            dataset_id="ds1",
            eval_id="e1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

        tracker.delete_annotation(exp_id, ann.id, "span")

        summary = tracker.get_eval_annotation_summary(exp_id, "ds1")
        assert len(summary.feedback) == 1


class TestUpdateAnnotation:
    def _span_annotation(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        trace_id: str = "t1",
        span_id: str = "s1",
    ) -> "AnnotationRecord":
        tracker.log_span(
            trace_id=trace_id,
            span_id=span_id,
            name="op",
            start_time_unix_nano=1_000_000,
            end_time_unix_nano=2_000_000,
            experiment_id=exp_id,
        )
        return tracker.log_span_annotation(
            trace_id=trace_id,
            span_id=span_id,
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

    def _eval_annotation(
        self, tracker: ExperimentTracker, exp_id: str
    ) -> "AnnotationRecord":
        tracker.log_eval_sample(
            eval_id="e1", dataset_id="ds1", inputs={"q": "hi"}, experiment_id=exp_id
        )
        return tracker.log_eval_annotation(
            dataset_id="ds1",
            eval_id="e1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

    def test_raises_when_no_annotation_tables(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "_has_annotation_tables", lambda _: False)

        with pytest.raises(ValueError, match="older schema"):
            tracker.update_annotation(exp_id, "any-id", "span", value=False)

    def test_raises_when_no_fields_provided(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        with pytest.raises(ValueError, match="No fields to update"):
            tracker.update_annotation(exp_id, "any-id", "span")

    def test_raises_when_annotation_not_found(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment

        with pytest.raises(ValueError, match="not found"):
            tracker.update_annotation(exp_id, "nonexistent-id", "span", value=False)

    def test_updates_span_annotation_value(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ann = self._span_annotation(tracker, exp_id)

        result = tracker.update_annotation(exp_id, ann.id, "span", value=False)

        assert result.value is False

    def test_updates_span_annotation_rationale(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ann = self._span_annotation(tracker, exp_id)

        result = tracker.update_annotation(
            exp_id, ann.id, "span", rationale="new rationale"
        )

        assert result.rationale == "new rationale"

    def test_updates_both_value_and_rationale(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ann = self._span_annotation(tracker, exp_id)

        result = tracker.update_annotation(
            exp_id, ann.id, "span", value=False, rationale="revised"
        )

        assert result.value is False
        assert result.rationale == "revised"

    def test_updates_eval_annotation(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        ann = self._eval_annotation(tracker, exp_id)

        result = tracker.update_annotation(
            exp_id, ann.id, "eval", value=False, rationale="wrong"
        )

        assert result.value is False
        assert result.rationale == "wrong"


class TestGetSpanAnnotations:
    def _log_span(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        trace_id: str,
        span_id: str,
    ) -> None:
        tracker.log_span(
            trace_id=trace_id,
            span_id=span_id,
            name="op",
            start_time_unix_nano=1_000_000,
            end_time_unix_nano=2_000_000,
            experiment_id=exp_id,
        )

    def _annotate(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        trace_id: str,
        span_id: str,
        name: str = "quality",
        value: bool = True,
        user: str = "alice",
    ) -> "AnnotationRecord":
        return tracker.log_span_annotation(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            annotation_kind="feedback",
            value_type="bool",
            value=value,
            user=user,
            experiment_id=exp_id,
        )

    def test_returns_empty_when_no_annotation_tables(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "_has_annotation_tables", lambda _: False)

        result = tracker.get_span_annotations(exp_id, "t1", "s1")

        assert result == []

    def test_returns_empty_when_no_annotations_for_span(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")

        result = tracker.get_span_annotations(exp_id, "t1", "s1")

        assert result == []

    def test_returns_annotation_fields(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._annotate(tracker, exp_id, "t1", "s1", name="quality", value=True)

        result = tracker.get_span_annotations(exp_id, "t1", "s1")

        assert len(result) == 1
        ann = result[0]
        assert isinstance(ann, AnnotationRecord)
        assert ann.name == "quality"
        assert ann.value is True
        assert ann.user == "alice"

    def test_returns_all_annotations_for_span(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._annotate(tracker, exp_id, "t1", "s1", name="quality", user="alice")
        self._annotate(tracker, exp_id, "t1", "s1", name="relevance", user="bob")

        result = tracker.get_span_annotations(exp_id, "t1", "s1")

        assert len(result) == 2
        assert {a.name for a in result} == {"quality", "relevance"}

    def test_scoped_to_span_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "t1", "s1")
        self._log_span(tracker, exp_id, "t1", "s2")
        self._annotate(tracker, exp_id, "t1", "s1", name="quality")
        self._annotate(tracker, exp_id, "t1", "s2", name="other")

        result = tracker.get_span_annotations(exp_id, "t1", "s1")

        assert len(result) == 1
        assert result[0].name == "quality"

    def test_scoped_to_trace_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id, "trace-a", "s1")
        self._log_span(tracker, exp_id, "trace-b", "s1")
        self._annotate(tracker, exp_id, "trace-a", "s1", name="quality")
        self._annotate(tracker, exp_id, "trace-b", "s1", name="other")

        result = tracker.get_span_annotations(exp_id, "trace-a", "s1")

        assert len(result) == 1
        assert result[0].name == "quality"


class TestLogSpanAnnotation:
    def _log_span(
        self,
        tracker: ExperimentTracker,
        exp_id: str,
        trace_id: str = "trace-1",
        span_id: str = "span-1",
    ) -> None:
        tracker.log_span(
            trace_id=trace_id,
            span_id=span_id,
            name="op",
            start_time_unix_nano=1_000_000,
            end_time_unix_nano=2_000_000,
            experiment_id=exp_id,
        )

    def test_raises_when_no_active_experiment(self, tracker: ExperimentTracker) -> None:
        with pytest.raises(ValueError, match="No active experiment"):
            tracker.log_span_annotation(
                trace_id="t1",
                span_id="s1",
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="alice",
            )

    def test_uses_current_experiment_when_id_not_provided(
        self, tracker: ExperimentTracker
    ) -> None:
        exp_id = tracker.start_experiment(name="current")
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )

        assert isinstance(result, AnnotationRecord)
        assert result.name == "quality"

    def test_uses_explicit_experiment_id(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

        assert isinstance(result, AnnotationRecord)

    def test_raises_for_feedback_with_non_bool_value_type(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        with pytest.raises(
            ValueError, match="Feedback annotations must use value_type='bool'"
        ):
            tracker.log_span_annotation(
                trace_id="trace-1",
                span_id="span-1",
                name="quality",
                annotation_kind="feedback",
                value_type="int",
                value=5,
                user="alice",
                experiment_id=exp_id,
            )

    def test_raises_when_no_annotation_tables(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        monkeypatch.setattr(tracker.backend, "_has_annotation_tables", lambda _: False)

        with pytest.raises(ValueError, match="older schema"):
            tracker.log_span_annotation(
                trace_id="trace-1",
                span_id="span-1",
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="alice",
                experiment_id=exp_id,
            )

    def test_feedback_bool_value_true(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

        assert result.annotation_kind.value == "feedback"
        assert result.value is True
        assert result.user == "alice"
        assert result.rationale is None

    def test_feedback_bool_value_false(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=False,
            user="bob",
            experiment_id=exp_id,
        )

        assert result.value is False

    def test_expectation_int_value(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="latency",
            annotation_kind="expectation",
            value_type="int",
            value=42,
            user="alice",
            experiment_id=exp_id,
        )

        assert result.annotation_kind.value == "expectation"
        assert result.value == 42

    def test_expectation_string_value(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="label",
            annotation_kind="expectation",
            value_type="string",
            value="good",
            user="alice",
            experiment_id=exp_id,
        )

        assert result.value == "good"

    def test_rationale_is_persisted(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            rationale="very relevant output",
            experiment_id=exp_id,
        )

        assert result.rationale == "very relevant output"

    def test_returned_record_has_id_and_created_at(
        self,
        tracker_with_experiment: tuple[ExperimentTracker, str],
    ) -> None:
        tracker, exp_id = tracker_with_experiment
        self._log_span(tracker, exp_id)

        result = tracker.log_span_annotation(
            trace_id="trace-1",
            span_id="span-1",
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            experiment_id=exp_id,
        )

        assert result.id is not None
        assert result.created_at is not None
