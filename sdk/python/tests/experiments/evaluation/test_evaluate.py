import warnings
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from luml.experiments.evaluation.evaluate import (
    _aggregate_scores,
    _call_scorer,
    _evaluate_single_item,
    evaluate,
)
from luml.experiments.evaluation.scorers.base import (
    BaseScorer,
    SupervisedScorer,
    UnsupervisedScorer,
)
from luml.experiments.evaluation.types import EvalItem, EvalResult


class MockUnsupervisedScorer(UnsupervisedScorer):
    def __init__(self, name: str = "mock_unsupervised") -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def score(
        self, inputs: dict[str, Any], output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return 0.8


class MockSupervisedScorer(SupervisedScorer):
    def __init__(self, name: str = "mock_supervised") -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def score(
        self, inputs: dict[str, Any], expected_output: Any, output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return expected_output == output


class MockDictScorer(UnsupervisedScorer):
    def __init__(self, name: str = "mock_dict") -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def score(
        self, inputs: dict[str, Any], output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return {"accuracy": 0.9, "precision": 0.85}


class MockInvalidScorer(BaseScorer):
    def get_name(self) -> str:
        return "invalid_scorer"


class TestCallScorer:
    def test_call_unsupervised_scorer(self) -> None:
        scorer = MockUnsupervisedScorer()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        result = _call_scorer(scorer, eval_item, "response")

        assert result == {"mock_unsupervised": 0.8}

    def test_call_supervised_scorer(self) -> None:
        scorer = MockSupervisedScorer()
        eval_item = EvalItem(
            id="1", inputs={"text": "hello"}, expected_output="response"
        )
        result = _call_scorer(scorer, eval_item, "response")

        assert result == {"mock_supervised": True}

    def test_call_supervised_scorer_without_expected_output_raises(self) -> None:
        scorer = MockSupervisedScorer()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})

        with pytest.raises(ValueError, match="requires expected_output"):
            _call_scorer(scorer, eval_item, "response")

    def test_call_scorer_with_dict_return(self) -> None:
        scorer = MockDictScorer()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        result = _call_scorer(scorer, eval_item, "response")

        assert result == {"accuracy": 0.9, "precision": 0.85}

    def test_call_scorer_with_bool_return(self) -> None:
        class BoolScorer(UnsupervisedScorer):
            def get_name(self) -> str:
                return "bool_scorer"

            def score(
                self, inputs: dict[str, Any], output: Any  # noqa: ANN401
            ) -> bool | float | int | dict[str, Any]:
                return True

        scorer = BoolScorer()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        result = _call_scorer(scorer, eval_item, "response")

        assert result == {"bool_scorer": True}

    def test_call_scorer_with_invalid_scorer_type_raises(self) -> None:
        scorer = MockInvalidScorer()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})

        with pytest.raises(TypeError, match="must be an instance"):
            _call_scorer(scorer, eval_item, "response")


class TestAggregateScores:
    def test_aggregate_empty_results(self) -> None:
        result = _aggregate_scores([])
        assert result == {}

    def test_aggregate_single_result(self) -> None:
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        results = [
            EvalResult(
                eval_item=eval_item,
                model_response="response",
                scores={"accuracy": 0.9},
                trace_id="trace-001",
            )
        ]
        aggregated = _aggregate_scores(results)

        assert aggregated["accuracy_mean"] == 0.9
        assert aggregated["accuracy_min"] == 0.9
        assert aggregated["accuracy_max"] == 0.9
        assert aggregated["accuracy_count"] == 1
        assert aggregated["total_items"] == 1
        assert aggregated["successful_items"] == 1

    def test_aggregate_multiple_results(self) -> None:
        eval_items = [
            EvalItem(id=str(i), inputs={"text": f"text_{i}"}) for i in range(3)
        ]
        results = [
            EvalResult(
                eval_item=eval_items[0],
                model_response="r1",
                scores={"accuracy": 0.8, "f1": 0.7},
                trace_id="trace-001",
            ),
            EvalResult(
                eval_item=eval_items[1],
                model_response="r2",
                scores={"accuracy": 0.9, "f1": 0.8},
                trace_id="trace-002",
            ),
            EvalResult(
                eval_item=eval_items[2],
                model_response="r3",
                scores={"accuracy": 0.7, "f1": 0.9},
                trace_id="trace-003",
            ),
        ]
        aggregated = _aggregate_scores(results)

        assert aggregated["accuracy_mean"] == pytest.approx(0.8, rel=1e-6)
        assert aggregated["accuracy_min"] == 0.7
        assert aggregated["accuracy_max"] == 0.9
        assert aggregated["accuracy_count"] == 3

        assert aggregated["f1_mean"] == pytest.approx(0.8, rel=1e-6)
        assert aggregated["f1_min"] == 0.7
        assert aggregated["f1_max"] == 0.9
        assert aggregated["f1_count"] == 3

        assert aggregated["total_items"] == 3
        assert aggregated["successful_items"] == 3

    def test_aggregate_skips_error_keys(self) -> None:
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        results = [
            EvalResult(
                eval_item=eval_item,
                model_response="response",
                scores={"accuracy": 0.9, "scorer_error": "Something went wrong"},
                trace_id="trace-001",
            )
        ]
        aggregated = _aggregate_scores(results)

        assert "scorer_error_mean" not in aggregated
        assert "accuracy_mean" in aggregated

    def test_aggregate_handles_bool_values(self) -> None:
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        results = [
            EvalResult(
                eval_item=eval_item,
                model_response="response",
                scores={"is_correct": True},
                trace_id="trace-001",
            ),
            EvalResult(
                eval_item=eval_item,
                model_response="response",
                scores={"is_correct": False},
                trace_id="trace-002",
            ),
        ]
        aggregated = _aggregate_scores(results)

        assert aggregated["is_correct_mean"] == 0.5
        assert aggregated["is_correct_min"] == 0.0
        assert aggregated["is_correct_max"] == 1.0

    def test_aggregate_counts_errors_in_successful_items(self) -> None:
        eval_items = [
            EvalItem(id=str(i), inputs={"text": f"text_{i}"}) for i in range(3)
        ]
        results = [
            EvalResult(
                eval_item=eval_items[0],
                model_response="r1",
                scores={"accuracy": 0.9},
                trace_id="trace-001",
            ),
            EvalResult(
                eval_item=eval_items[1],
                model_response=None,
                scores={"error": "LLM call failed"},
                trace_id="trace-002",
            ),
            EvalResult(
                eval_item=eval_items[2],
                model_response="r3",
                scores={"accuracy": 0.8},
                trace_id="trace-003",
            ),
        ]
        aggregated = _aggregate_scores(results)

        assert aggregated["total_items"] == 3
        assert aggregated["successful_items"] == 2


class TestEvaluateSingleItem:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_successful_evaluation(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        mock_tracker = MagicMock()
        eval_item = EvalItem(
            id="1", inputs={"text": "hello"}, expected_output="world"
        )
        scorer = MockSupervisedScorer()

        def inference_fn(inputs: dict[str, Any]) -> str:
            return "world"

        result = _evaluate_single_item(
            eval_item=eval_item,
            inference_fn=inference_fn,
            scorers=[scorer],
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            tracer=mock_tracer,
        )

        assert result.eval_item == eval_item
        assert result.model_response == "world"
        assert result.scores == {"mock_supervised": True}
        mock_tracker.log_eval_sample.assert_called_once()
        mock_tracker.link_eval_sample_to_trace.assert_called_once()

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_inference_fn_failure(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        mock_tracker = MagicMock()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})
        scorer = MockUnsupervisedScorer()

        def failing_inference_fn(inputs: dict[str, Any]) -> str:
            raise RuntimeError("API error")

        result = _evaluate_single_item(
            eval_item=eval_item,
            inference_fn=failing_inference_fn,
            scorers=[scorer],
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            tracer=mock_tracer,
        )

        assert result.model_response is None
        assert "error" in result.scores
        assert "API error" in str(result.scores["error"])

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_scorer_failure_captured(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        class FailingScorer(UnsupervisedScorer):
            def get_name(self) -> str:
                return "failing_scorer"

            def score(
                self, inputs: dict[str, Any], output: Any  # noqa: ANN401
            ) -> bool | float | int | dict[str, Any]:
                raise ValueError("Scoring failed")

        mock_tracker = MagicMock()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})

        def inference_fn(inputs: dict[str, Any]) -> str:
            return "response"

        result = _evaluate_single_item(
            eval_item=eval_item,
            inference_fn=inference_fn,
            scorers=[FailingScorer()],
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            tracer=mock_tracer,
        )

        assert "failing_scorer_error" in result.scores
        assert "Scoring failed" in str(result.scores["failing_scorer_error"])

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_duplicate_score_keys_warning(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        class DuplicateKeyScorer1(UnsupervisedScorer):
            def get_name(self) -> str:
                return "scorer1"

            def score(
                self, inputs: dict[str, Any], output: Any  # noqa: ANN401
            ) -> bool | float | int | dict[str, Any]:
                return {"shared_key": 0.5}

        class DuplicateKeyScorer2(UnsupervisedScorer):
            def get_name(self) -> str:
                return "scorer2"

            def score(
                self, inputs: dict[str, Any], output: Any  # noqa: ANN401
            ) -> bool | float | int | dict[str, Any]:
                return {"shared_key": 0.8}

        mock_tracker = MagicMock()
        eval_item = EvalItem(id="1", inputs={"text": "hello"})

        def inference_fn(inputs: dict[str, Any]) -> str:
            return "response"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _evaluate_single_item(
                eval_item=eval_item,
                inference_fn=inference_fn,
                scorers=[DuplicateKeyScorer1(), DuplicateKeyScorer2()],
                dataset_id="test_dataset",
                experiment_tracker=mock_tracker,
                tracer=mock_tracer,
            )

            assert len(w) == 1
            assert "Duplicate score keys" in str(w[0].message)

        assert result.scores["shared_key"] == 0.8


class TestEvaluate:
    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_evaluate_single_item(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        mock_tracker = MagicMock()
        eval_dataset = [EvalItem(id="1", inputs={"text": "hello"})]
        scorer = MockUnsupervisedScorer()

        def inference_fn(inputs: dict[str, Any]) -> str:
            return "response"

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=inference_fn,
            scorers=[scorer],
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            n_threads=1,
        )

        assert len(results.results) == 1
        assert results.dataset_id == "test_dataset"
        assert "mock_unsupervised_mean" in results.aggregated_scores
        assert results.aggregated_scores["total_items"] == 1

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_evaluate_multiple_items(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        mock_tracker = MagicMock()
        eval_dataset = [
            EvalItem(id=str(i), inputs={"text": f"text_{i}"}) for i in range(5)
        ]
        scorer = MockUnsupervisedScorer()

        def inference_fn(inputs: dict[str, Any]) -> str:
            return "response"

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=inference_fn,
            scorers=[scorer],
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            n_threads=1,
        )

        assert len(results.results) == 5
        assert results.aggregated_scores["total_items"] == 5
        assert results.aggregated_scores["successful_items"] == 5

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_evaluate_parallel_execution(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        mock_tracker = MagicMock()
        eval_dataset = [
            EvalItem(id=str(i), inputs={"text": f"text_{i}"}) for i in range(10)
        ]
        scorer = MockUnsupervisedScorer()

        call_count = 0

        def inference_fn(inputs: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            return "response"

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=inference_fn,
            scorers=[scorer],
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            n_threads=4,
        )

        assert len(results.results) == 10
        assert call_count == 10

    @patch("luml.experiments.evaluation.evaluate.trace")
    def test_evaluate_with_multiple_scorers(self, mock_trace: Mock) -> None:
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_span.context.trace_id = 12345
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(
            return_value=mock_span
        )
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(
            return_value=None
        )

        mock_tracker = MagicMock()
        eval_dataset = [
            EvalItem(
                id="1", inputs={"text": "hello"}, expected_output="response"
            )
        ]
        scorers = [MockUnsupervisedScorer(), MockSupervisedScorer()]

        def inference_fn(inputs: dict[str, Any]) -> str:
            return "response"

        results = evaluate(
            eval_dataset=eval_dataset,
            inference_fn=inference_fn,
            scorers=scorers,
            dataset_id="test_dataset",
            experiment_tracker=mock_tracker,
            n_threads=1,
        )

        assert len(results.results) == 1
        assert "mock_unsupervised" in results.results[0].scores
        assert "mock_supervised" in results.results[0].scores
