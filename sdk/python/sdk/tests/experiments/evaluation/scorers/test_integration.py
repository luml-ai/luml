import json
import warnings
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import StatusCode

from luml.experiments.evaluation import (
    EvalItem,
    unsupervised_scorer,
)
from luml.experiments.evaluation.evaluate import evaluate
from luml.experiments.evaluation.scorers.builtin import (
    Completeness,
    Correctness,
    PromptAlignment,
    Relevancy,
)
from luml.experiments.evaluation.scorers.builtin._prompts import CORRECTIVE_REMINDER
from luml.llm import LLMClient


class _InMemoryExporter(SpanExporter):
    def __init__(self) -> None:
        self._spans: list[ReadableSpan] = []

    def export(self, spans: Any) -> SpanExportResult:  # noqa: ANN401
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self._spans)


def _mock_client(response: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps(response)
    return client


def _make_tracker() -> MagicMock:
    tracker = MagicMock()
    tracker.log_eval_sample = MagicMock()
    tracker.link_eval_sample_to_trace = MagicMock()
    return tracker


def _mock_tracer() -> MagicMock:
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.context.trace_id = 12345
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
        return_value=mock_span
    )
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)
    return mock_tracer


class TestMixedBuiltinAndCustomScorers:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_builtin_and_custom_scorers_coexist(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "relevant", "score": 0.85})

        @unsupervised_scorer
        def is_short(
            inputs: dict[str, Any],  # noqa: ANN401
            output: Any,  # noqa: ANN401
        ) -> bool:
            return len(str(output)) < 100

        eval_dataset = [EvalItem(id="1", inputs={"question": "What is RAG?"})]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "RAG is retrieval-augmented generation.",
            scorers=[Relevancy(client=client), is_short],
            dataset_id="mixed_v1",
            experiment_tracker=tracker,
        )

        scores = results.results[0].scores
        assert "relevancy" in scores
        assert scores["relevancy"] == 0.85
        assert "is_short" in scores
        assert scores["is_short"] is True
        assert "relevancy_reasoning" not in scores

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_supervised_and_unsupervised_coexist(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        relevancy_client = _mock_client({"reasoning": "relevant", "score": 0.9})
        correctness_client = _mock_client({"reasoning": "correct", "score": 0.8})

        eval_dataset = [
            EvalItem(
                id="1",
                inputs={"question": "What is RAG?"},
                expected_output={
                    "expected_facts": ["RAG combines retrieval with generation"]
                },
            )
        ]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "RAG is great.",
            scorers=[
                Relevancy(client=relevancy_client),
                Correctness(client=correctness_client),
            ],
            dataset_id="mixed_v1",
            experiment_tracker=tracker,
        )

        scores = results.results[0].scores
        assert "relevancy" in scores
        assert "correctness" in scores
        assert scores["relevancy"] == 0.9
        assert scores["correctness"] == 0.8


class TestReasoningRoutingEndToEnd:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_reasoning_in_metadata_not_scores(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "Very relevant answer", "score": 0.9})

        eval_dataset = [
            EvalItem(
                id="1",
                inputs={"question": "What is RAG?"},
                metadata={"source": "test"},
            )
        ]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "RAG is ...",
            scorers=[Relevancy(client=client)],
            dataset_id="v1",
            experiment_tracker=tracker,
        )

        scores = results.results[0].scores
        assert scores == {"relevancy": 0.9}
        assert "relevancy_reasoning" not in scores

        call_kwargs = tracker.log_eval_sample.call_args
        logged_scores = call_kwargs.kwargs.get("scores", call_kwargs[1].get("scores"))
        logged_metadata = call_kwargs.kwargs.get(
            "metadata", call_kwargs[1].get("metadata")
        )
        assert "relevancy" in logged_scores
        assert "relevancy_reasoning" not in logged_scores
        assert logged_metadata["relevancy_reasoning"] == "Very relevant answer"
        assert logged_metadata["source"] == "test"

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_aggregated_scores_numeric_only(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "ok", "score": 0.8})

        eval_dataset = [
            EvalItem(id=str(i), inputs={"question": f"Q{i}"}) for i in range(3)
        ]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "answer",
            scorers=[Relevancy(client=client)],
            dataset_id="v1",
            experiment_tracker=tracker,
        )

        agg = results.aggregated_scores
        assert "relevancy_mean" in agg
        assert "relevancy_min" in agg
        assert "relevancy_max" in agg
        assert "relevancy_count" in agg
        for key in agg:
            assert "reasoning" not in key


class TestDuplicateScorerNames:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_duplicate_names_warn(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "ok", "score": 0.7})

        eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
        tracker = _make_tracker()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            evaluate(
                eval_dataset=eval_dataset,
                inference_fn=lambda inputs: "A",
                scorers=[Relevancy(client=client), Relevancy(client=client)],
                dataset_id="v1",
                experiment_tracker=tracker,
            )
            dup_warnings = [x for x in w if "Duplicate score keys" in str(x.message)]
            assert len(dup_warnings) >= 1

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_custom_names_avoid_duplicates(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "ok", "score": 0.7})

        eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
        tracker = _make_tracker()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            results = evaluate(
                eval_dataset=eval_dataset,
                inference_fn=lambda inputs: "A",
                scorers=[
                    Relevancy(client=client, name="relevancy_1"),
                    Relevancy(client=client, name="relevancy_2"),
                ],
                dataset_id="v1",
                experiment_tracker=tracker,
            )
            dup_warnings = [x for x in w if "Duplicate score keys" in str(x.message)]
            assert len(dup_warnings) == 0

        scores = results.results[0].scores
        assert "relevancy_1" in scores
        assert "relevancy_2" in scores


class TestErrorIsolation:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_one_scorer_error_does_not_block_others(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        good_client = _mock_client({"reasoning": "ok", "score": 0.85})
        bad_client = MagicMock(spec=LLMClient)
        bad_client.complete.return_value = "not json at all"

        eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "A",
            scorers=[
                Relevancy(client=bad_client, name="bad_relevancy"),
                Relevancy(client=good_client, name="good_relevancy"),
            ],
            dataset_id="v1",
            experiment_tracker=tracker,
        )

        scores = results.results[0].scores
        assert "__error__bad_relevancy" in scores
        assert scores["good_relevancy"] == 0.85


class TestCorrectiveRetryPath:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_bad_json_then_good_json_succeeds(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = MagicMock(spec=LLMClient)
        client.complete.side_effect = [
            "this is not json",
            json.dumps({"reasoning": "ok", "score": 0.75}),
        ]

        eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "A",
            scorers=[Relevancy(client=client)],
            dataset_id="v1",
            experiment_tracker=tracker,
        )

        scores = results.results[0].scores
        assert scores["relevancy"] == 0.75
        assert client.complete.call_count == 2
        retry_user_prompt = client.complete.call_args_list[1][0][1]
        assert CORRECTIVE_REMINDER in retry_user_prompt


class TestMultiThreadedEvaluation:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_builtin_scorers_with_threads(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "ok", "score": 0.8})

        eval_dataset = [
            EvalItem(id=str(i), inputs={"question": f"Q{i}"}) for i in range(6)
        ]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "answer",
            scorers=[Relevancy(client=client)],
            dataset_id="v1",
            experiment_tracker=tracker,
            n_threads=2,
        )

        assert len(results.results) == 6
        assert results.aggregated_scores["total_items"] == 6
        assert results.aggregated_scores["successful_items"] == 6
        for r in results.results:
            assert r.scores["relevancy"] == 0.8


class TestCustomLLMClient:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_custom_client_no_openai_needed(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()

        class MyClient:
            def complete(self, system_prompt: str, user_prompt: str) -> str:
                return json.dumps({"reasoning": "custom", "score": 0.77})

        custom = MyClient()

        eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "A",
            scorers=[Relevancy(client=custom)],
            dataset_id="v1",
            experiment_tracker=tracker,
        )

        assert results.results[0].scores["relevancy"] == 0.77

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_shared_client_across_scorers(self, mock_trace: Mock) -> None:
        mock_trace.get_tracer.return_value = _mock_tracer()
        client = _mock_client({"reasoning": "ok", "score": 0.6})

        eval_dataset = [
            EvalItem(id="1", inputs={"question": "Q", "instructions": "Do X"})
        ]
        tracker = _make_tracker()

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=lambda inputs: "A",
            scorers=[
                Relevancy(client=client),
                Completeness(client=client),
                PromptAlignment(client=client),
            ],
            dataset_id="v1",
            experiment_tracker=tracker,
        )

        scores = results.results[0].scores
        assert "relevancy" in scores
        assert "completeness" in scores
        assert "prompt_alignment" in scores
        assert client.complete.call_count == 3


class TestTracingEndToEnd:
    def test_evaluate_produces_span_tree(self) -> None:
        exporter = _InMemoryExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        eval_tracer = provider.get_tracer("luml.experiments.evaluation.evaluate")
        base_tracer = provider.get_tracer(
            "luml.experiments.evaluation.scorers.builtin._base"
        )

        with (
            patch("luml.experiments.evaluation.evaluate.trace") as mock_trace,
            patch(
                "luml.experiments.evaluation.scorers.builtin._base._tracer",
                base_tracer,
            ),
        ):
            mock_trace.get_tracer.return_value = eval_tracer

            client = _mock_client({"reasoning": "ok", "score": 0.8})
            eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
            tracker = _make_tracker()

            evaluate(
                eval_dataset=eval_dataset,
                inference_fn=lambda inputs: "A",
                scorers=[Relevancy(client=client)],
                dataset_id="v1",
                experiment_tracker=tracker,
            )

        provider.force_flush()
        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]

        assert "eval_request" in span_names
        assert "eval_scoring" in span_names
        assert "llm_judge" in span_names

        judge_span = next(s for s in spans if s.name == "llm_judge")
        assert judge_span.attributes is not None
        assert judge_span.attributes["eval.scorer.name"] == "relevancy"
        assert judge_span.attributes["eval.scorer.score"] == 0.8

        scoring_span = next(s for s in spans if s.name == "eval_scoring")
        assert judge_span.parent is not None
        assert judge_span.parent.span_id == scoring_span.context.span_id

    def test_judge_error_marks_span_error(self) -> None:
        exporter = _InMemoryExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))

        eval_tracer = provider.get_tracer("luml.experiments.evaluation.evaluate")
        base_tracer = provider.get_tracer(
            "luml.experiments.evaluation.scorers.builtin._base"
        )

        with (
            patch("luml.experiments.evaluation.evaluate.trace") as mock_trace,
            patch(
                "luml.experiments.evaluation.scorers.builtin._base._tracer",
                base_tracer,
            ),
        ):
            mock_trace.get_tracer.return_value = eval_tracer

            bad_client = MagicMock(spec=LLMClient)
            bad_client.complete.return_value = "not json"

            eval_dataset = [EvalItem(id="1", inputs={"question": "Q"})]
            tracker = _make_tracker()

            results = evaluate(
                eval_dataset=eval_dataset,
                inference_fn=lambda inputs: "A",
                scorers=[Relevancy(client=bad_client)],
                dataset_id="v1",
                experiment_tracker=tracker,
            )

            assert "__error__relevancy" in results.results[0].scores

        provider.force_flush()
        spans = exporter.get_finished_spans()
        judge_span = next((s for s in spans if s.name == "llm_judge"), None)
        assert judge_span is not None
        assert judge_span.status.status_code == StatusCode.ERROR
        events = judge_span.events or ()
        exception_events = [e for e in events if e.name == "exception"]
        assert len(exception_events) >= 1
