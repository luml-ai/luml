from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.handlers.annotations import AnnotationsHandler
from lumlflow.handlers.experiments import ExperimentsHandler
from lumlflow.infra.exceptions import ApplicationError, NotFound
from lumlflow.schemas.annotations import (
    Annotation,
    CreateAnnotation,
    UpdateAnnotation,
)


@pytest.fixture
def handler(tmp_path: Path) -> AnnotationsHandler:
    tracker = ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")
    handler = AnnotationsHandler(tracker=tracker)
    return handler


@pytest.fixture
def handler_with_experiment(
    handler: AnnotationsHandler,
) -> tuple[AnnotationsHandler, str]:
    exp_id = handler.tracker.start_experiment(name="test", experiment_id="test-exp")
    return handler, exp_id


def _seed_eval(handler: AnnotationsHandler, exp_id: str) -> tuple[str, str]:
    dataset_id = "ds-1"
    eval_id = "eval-1"
    handler.tracker.log_eval_sample(
        eval_id=eval_id,
        dataset_id=dataset_id,
        inputs={"prompt": "hello"},
        experiment_id=exp_id,
    )
    return dataset_id, eval_id


def _seed_span(handler: AnnotationsHandler, exp_id: str) -> tuple[str, str]:
    trace_id = "trace-1"
    span_id = "span-1"
    handler.tracker.log_span(
        trace_id=trace_id,
        span_id=span_id,
        name="test-span",
        start_time_unix_nano=0,
        end_time_unix_nano=1000,
        experiment_id=exp_id,
    )
    return trace_id, span_id


class TestEvalAnnotationHandler:
    def test_create_and_get_eval_annotation(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="accuracy",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        result = handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)

        assert isinstance(result, Annotation)
        assert result.name == "accuracy"
        assert result.value is True
        assert result.user == "alice"
        assert result.rationale is None

        annotations = handler.get_eval_annotations(exp_id, dataset_id, eval_id)
        assert len(annotations) == 1
        assert annotations[0].id == result.id
        assert annotations[0].name == "accuracy"

    def test_create_annotation_with_rationale(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="accuracy",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
            rationale="The answer is correct",
        )
        result = handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)

        assert result.rationale == "The answer is correct"

        annotations = handler.get_eval_annotations(exp_id, dataset_id, eval_id)
        assert annotations[0].rationale == "The answer is correct"

    def test_delete_eval_annotation(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        result = handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)
        handler.delete_eval_annotation(exp_id, result.id)

        annotations = handler.get_eval_annotations(exp_id, dataset_id, eval_id)
        assert len(annotations) == 0

    def test_feedback_non_bool_raises(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="string",
            value="bad",
            user="alice",
        )
        with pytest.raises(ApplicationError, match="value_type='bool'"):
            handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)


class TestSpanAnnotationHandler:
    def test_create_and_get_span_annotation(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        body = CreateAnnotation(
            name="latency",
            annotation_kind="expectation",
            value_type="int",
            value=42,
            user="bob",
        )
        result = handler.create_span_annotation(exp_id, trace_id, span_id, body)

        assert isinstance(result, Annotation)
        assert result.name == "latency"
        assert result.value == 42

        annotations = handler.get_span_annotations(exp_id, trace_id, span_id)
        assert len(annotations) == 1
        assert annotations[0].id == result.id
        assert annotations[0].name == "latency"

    def test_delete_span_annotation(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=False,
            user="carol",
        )
        result = handler.create_span_annotation(exp_id, trace_id, span_id, body)
        handler.delete_span_annotation(exp_id, result.id)

        annotations = handler.get_span_annotations(exp_id, trace_id, span_id)
        assert len(annotations) == 0


class TestAnnotationCountInTrace:
    def test_span_annotation_count_propagates(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        exp_handler = ExperimentsHandler(tracker=handler.tracker)

        result = exp_handler.get_trace(exp_id, trace_id)
        assert result.spans[0].annotation_count == 0

        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        handler.create_span_annotation(exp_id, trace_id, span_id, body)

        result = exp_handler.get_trace(exp_id, trace_id)
        assert result.spans[0].annotation_count == 1


class TestHandlerExperimentNotFound:
    def test_create_eval_annotation_404(self, handler: AnnotationsHandler) -> None:
        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        with pytest.raises(NotFound):
            handler.create_eval_annotation("nonexistent", "ds", "eval", body)

    def test_get_eval_annotations_404(self, handler: AnnotationsHandler) -> None:
        with pytest.raises(NotFound):
            handler.get_eval_annotations("nonexistent", "ds", "eval")

    def test_create_span_annotation_404(self, handler: AnnotationsHandler) -> None:
        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        with pytest.raises(NotFound):
            handler.create_span_annotation("nonexistent", "trace", "span", body)


class TestEvalAnnotationSummary:
    def test_empty_summary(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        _seed_eval(handler, exp_id)
        summary = handler.get_eval_annotation_summary(exp_id, "ds-1")
        assert summary.feedback == []
        assert summary.expectations == []

    def test_grouped_by_name(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        handler.create_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            CreateAnnotation(
                name="accuracy",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="a",
            ),
        )
        handler.create_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            CreateAnnotation(
                name="accuracy",
                annotation_kind="feedback",
                value_type="bool",
                value=False,
                user="b",
            ),
        )
        handler.create_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            CreateAnnotation(
                name="relevance",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="c",
            ),
        )
        handler.create_eval_annotation(
            exp_id,
            dataset_id,
            eval_id,
            CreateAnnotation(
                name="score",
                annotation_kind="expectation",
                value_type="int",
                value=5,
                user="d",
            ),
        )

        summary = handler.get_eval_annotation_summary(exp_id, dataset_id)

        assert len(summary.feedback) == 2
        fb_by_name = {f.name: f for f in summary.feedback}
        assert fb_by_name["accuracy"].total == 2
        assert fb_by_name["accuracy"].counts == {"true": 1, "false": 1}
        assert fb_by_name["relevance"].total == 1
        assert fb_by_name["relevance"].counts == {"true": 1}

        assert len(summary.expectations) == 1
        assert summary.expectations[0].name == "score"
        assert summary.expectations[0].total == 1

    def test_dataset_filtering(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        _seed_eval(handler, exp_id)

        handler.tracker.log_eval_sample(
            eval_id="eval-2",
            dataset_id="ds-2",
            inputs={"x": 1},
            experiment_id=exp_id,
        )
        handler.create_eval_annotation(
            exp_id,
            "ds-1",
            "eval-1",
            CreateAnnotation(
                name="accuracy",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="a",
            ),
        )
        handler.create_eval_annotation(
            exp_id,
            "ds-2",
            "eval-2",
            CreateAnnotation(
                name="accuracy",
                annotation_kind="feedback",
                value_type="bool",
                value=False,
                user="b",
            ),
        )

        s1 = handler.get_eval_annotation_summary(exp_id, "ds-1")
        assert len(s1.feedback) == 1
        assert s1.feedback[0].counts == {"true": 1}

        s2 = handler.get_eval_annotation_summary(exp_id, "ds-2")
        assert len(s2.feedback) == 1
        assert s2.feedback[0].counts == {"false": 1}


class TestTraceAnnotationSummary:
    def test_empty_summary(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        _seed_span(handler, exp_id)
        summary = handler.get_trace_annotation_summary(exp_id, "trace-1")
        assert summary.feedback == []
        assert summary.expectations == []

    def test_cross_span_grouped_by_name(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        handler.tracker.log_span(
            trace_id=trace_id,
            span_id="span-2",
            name="span-2",
            start_time_unix_nano=0,
            end_time_unix_nano=1000,
            experiment_id=exp_id,
        )

        handler.create_span_annotation(
            exp_id,
            trace_id,
            span_id,
            CreateAnnotation(
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="a",
            ),
        )
        handler.create_span_annotation(
            exp_id,
            trace_id,
            "span-2",
            CreateAnnotation(
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=False,
                user="b",
            ),
        )
        handler.create_span_annotation(
            exp_id,
            trace_id,
            "span-2",
            CreateAnnotation(
                name="latency",
                annotation_kind="expectation",
                value_type="int",
                value=100,
                user="c",
            ),
        )

        summary = handler.get_trace_annotation_summary(exp_id, trace_id)

        assert len(summary.feedback) == 1
        assert summary.feedback[0].name == "quality"
        assert summary.feedback[0].total == 2
        assert summary.feedback[0].counts == {"true": 1, "false": 1}

        assert len(summary.expectations) == 1
        assert summary.expectations[0].name == "latency"
        assert summary.expectations[0].total == 1


class TestAutoUser:
    def test_eval_annotation_defaults_to_system_user(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="accuracy",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
        )
        result = handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)
        assert result.user != ""
        assert isinstance(result.user, str)

    def test_span_annotation_defaults_to_system_user(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
        )
        result = handler.create_span_annotation(exp_id, trace_id, span_id, body)
        assert result.user != ""
        assert isinstance(result.user, str)

    def test_explicit_user_not_overridden(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="accuracy",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="explicit-user",
        )
        result = handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)
        assert result.user == "explicit-user"


class TestUpdateAnnotation:
    def test_update_eval_annotation(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        dataset_id, eval_id = _seed_eval(handler, exp_id)

        body = CreateAnnotation(
            name="accuracy",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        created = handler.create_eval_annotation(exp_id, dataset_id, eval_id, body)

        updated = handler.update_eval_annotation(
            exp_id,
            created.id,
            UpdateAnnotation(
                value=False,
                rationale="Was wrong",
            ),
        )
        assert updated.value is False
        assert updated.rationale == "Was wrong"

    def test_update_span_annotation(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        body = CreateAnnotation(
            name="quality",
            annotation_kind="feedback",
            value_type="bool",
            value=True,
            user="alice",
        )
        created = handler.create_span_annotation(exp_id, trace_id, span_id, body)

        updated = handler.update_span_annotation(
            exp_id,
            created.id,
            UpdateAnnotation(rationale="Added note"),
        )
        assert updated.value is True
        assert updated.rationale == "Added note"


class TestAllTracesAnnotationSummary:
    def test_aggregates_across_traces(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        handler.tracker.log_span(
            trace_id="trace-2",
            span_id="span-2",
            name="span-2",
            start_time_unix_nano=0,
            end_time_unix_nano=1000,
            experiment_id=exp_id,
        )

        handler.create_span_annotation(
            exp_id,
            trace_id,
            span_id,
            CreateAnnotation(
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="a",
            ),
        )
        handler.create_span_annotation(
            exp_id,
            "trace-2",
            "span-2",
            CreateAnnotation(
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=False,
                user="b",
            ),
        )

        summary = handler.get_all_traces_annotation_summary(exp_id)
        assert len(summary.feedback) == 1
        assert summary.feedback[0].total == 2
        assert summary.feedback[0].counts == {"true": 1, "false": 1}


class TestTraceSummaryInTraceResponse:
    def test_get_trace_includes_summary(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        handler.create_span_annotation(
            exp_id,
            trace_id,
            span_id,
            CreateAnnotation(
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="a",
            ),
        )

        exp_handler = ExperimentsHandler(tracker=handler.tracker)
        result = exp_handler.get_trace(exp_id, trace_id)
        assert result.annotations is not None
        assert len(result.annotations.feedback) == 1
        assert result.annotations.feedback[0].name == "quality"

    def test_get_traces_includes_summary(
        self, handler_with_experiment: tuple[AnnotationsHandler, str]
    ) -> None:
        handler, exp_id = handler_with_experiment
        trace_id, span_id = _seed_span(handler, exp_id)

        handler.create_span_annotation(
            exp_id,
            trace_id,
            span_id,
            CreateAnnotation(
                name="quality",
                annotation_kind="feedback",
                value_type="bool",
                value=True,
                user="a",
            ),
        )

        exp_handler = ExperimentsHandler(tracker=handler.tracker)
        result = exp_handler.get_experiment_traces(exp_id)
        assert len(result.items) == 1
        assert result.items[0].annotations is not None
        assert len(result.items[0].annotations.feedback) == 1
