import sqlite3
from pathlib import Path

import pytest

from luml.experiments.backends.data_types import (
    AnnotationKind,
    AnnotationRecord,
    AnnotationSummary,
    AnnotationValueType,
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


def _seed_span(backend: SQLiteBackend, experiment_id: str) -> tuple[str, str]:
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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        dataset_id, eval_id = _seed_eval(backend, exp_id)

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
        trace_id, span_id = _seed_span(backend, exp_id)

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
        trace_id, span_id = _seed_span(backend, exp_id)

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
        trace_id, span_id = _seed_span(backend, exp_id)

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
        trace_id, span_id = _seed_span(backend, exp_id)

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
        trace_id, span_id = _seed_span(backend, exp_id)

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

        dataset_id, eval_id = _seed_eval(backend, exp_id)
        trace_id, span_id = _seed_span(backend, exp_id)

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

        dataset_id, eval_id = _seed_eval(backend, exp_id)
        trace_id, span_id = _seed_span(backend, exp_id)

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
