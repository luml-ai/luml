from typing import Any

import pytest

from luml.experiments.evaluation.scorers.base import (
    BaseScorer,
    SupervisedFuncScorer,
    SupervisedScorer,
    UnsupervisedFuncScorer,
    UnsupervisedScorer,
    supervised_scorer,
    unsupervised_scorer,
)


class ConcreteUnsupervisedScorer(UnsupervisedScorer):
    def get_name(self) -> str:
        return "concrete_unsupervised"

    def score(
        self, inputs: dict[str, Any], output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return len(output) > 0


class ConcreteSupervisedScorer(SupervisedScorer):
    def get_name(self) -> str:
        return "concrete_supervised"

    def score(
        self, inputs: dict[str, Any], expected_output: Any, output: Any  # noqa: ANN401
    ) -> bool | float | int | dict[str, Any]:
        return expected_output == output


class TestUnsupervisedScorer:
    def test_get_name(self) -> None:
        scorer = ConcreteUnsupervisedScorer()
        assert scorer.get_name() == "concrete_unsupervised"

    def test_repr(self) -> None:
        scorer = ConcreteUnsupervisedScorer()
        assert repr(scorer) == "Scorer[concrete_unsupervised]"

    def test_score(self) -> None:
        scorer = ConcreteUnsupervisedScorer()
        result = scorer.score({"text": "hello"}, "world")
        assert result is True

        result = scorer.score({"text": "hello"}, "")
        assert result is False


class TestSupervisedScorer:
    def test_get_name(self) -> None:
        scorer = ConcreteSupervisedScorer()
        assert scorer.get_name() == "concrete_supervised"

    def test_repr(self) -> None:
        scorer = ConcreteSupervisedScorer()
        assert repr(scorer) == "Scorer[concrete_supervised]"

    def test_score_match(self) -> None:
        scorer = ConcreteSupervisedScorer()
        result = scorer.score({"text": "hello"}, "world", "world")
        assert result is True

    def test_score_no_match(self) -> None:
        scorer = ConcreteSupervisedScorer()
        result = scorer.score({"text": "hello"}, "world", "universe")
        assert result is False


class TestUnsupervisedFuncScorer:
    def test_init_and_get_name(self) -> None:
        def my_scorer(inputs: dict[str, Any], output: Any) -> float:  # noqa: ANN401
            return 0.5

        scorer = UnsupervisedFuncScorer(name="my_scorer", score_fn=my_scorer)
        assert scorer.get_name() == "my_scorer"

    def test_score(self) -> None:
        def length_scorer(inputs: dict[str, Any], output: Any) -> int:  # noqa: ANN401
            return len(output)

        scorer = UnsupervisedFuncScorer(name="length_scorer", score_fn=length_scorer)
        result = scorer.score({"text": "hello"}, "world")
        assert result == 5

    def test_score_returns_dict(self) -> None:
        def multi_scorer(inputs: dict[str, Any], output: Any) -> dict[str, float]:  # noqa: ANN401
            return {"metric_a": 0.8, "metric_b": 0.9}

        scorer = UnsupervisedFuncScorer(name="multi_scorer", score_fn=multi_scorer)
        result = scorer.score({"text": "hello"}, "world")
        assert result == {"metric_a": 0.8, "metric_b": 0.9}


class TestSupervisedFuncScorer:
    def test_init_and_get_name(self) -> None:
        def my_scorer(
            inputs: dict[str, Any], expected: Any, output: Any  # noqa: ANN401
        ) -> bool:
            return expected == output

        scorer = SupervisedFuncScorer(name="my_scorer", score_fn=my_scorer)
        assert scorer.get_name() == "my_scorer"

    def test_score(self) -> None:
        def exact_match(
            inputs: dict[str, Any], expected: Any, output: Any  # noqa: ANN401
        ) -> bool:
            return expected == output

        scorer = SupervisedFuncScorer(name="exact_match", score_fn=exact_match)

        result = scorer.score({"text": "hello"}, "world", "world")
        assert result is True

        result = scorer.score({"text": "hello"}, "world", "universe")
        assert result is False

    def test_score_returns_float(self) -> None:
        def similarity_scorer(
            inputs: dict[str, Any], expected: Any, output: Any  # noqa: ANN401
        ) -> float:
            if expected == output:
                return 1.0
            return len(set(expected) & set(output)) / len(set(expected) | set(output))

        scorer = SupervisedFuncScorer(
            name="similarity_scorer", score_fn=similarity_scorer
        )
        result = scorer.score({}, "hello", "hello")
        assert result == 1.0


class TestUnsupervisedScoreDecorator:
    def test_decorator_creates_scorer(self) -> None:
        @unsupervised_scorer
        def my_unsupervised_scorer(inputs: dict[str, Any], output: Any) -> float:  # noqa: ANN401
            return 0.75

        assert isinstance(my_unsupervised_scorer, UnsupervisedFuncScorer)
        assert my_unsupervised_scorer.get_name() == "my_unsupervised_scorer"

    def test_decorator_scorer_works(self) -> None:
        @unsupervised_scorer
        def output_length(inputs: dict[str, Any], output: Any) -> int:  # noqa: ANN401
            return len(output)

        result = output_length.score({"text": "test"}, "hello world")
        assert result == 11

    def test_decorator_with_dict_return(self) -> None:
        @unsupervised_scorer
        def multi_metric(inputs: dict[str, Any], output: Any) -> dict[str, float]:  # noqa: ANN401
            return {"length": len(output), "has_content": len(output) > 0}

        result = multi_metric.score({}, "test")
        assert result == {"length": 4, "has_content": True}

    def test_decorator_with_lambda_uses_lambda_name(self) -> None:
        scorer = unsupervised_scorer(lambda inputs, output: 0.5)
        assert scorer.get_name() == "<lambda>"


class TestSupervisedScoreDecorator:
    def test_decorator_creates_scorer(self) -> None:
        @supervised_scorer
        def my_supervised_scorer(
            inputs: dict[str, Any], expected: Any, output: Any  # noqa: ANN401
        ) -> bool:
            return expected == output

        assert isinstance(my_supervised_scorer, SupervisedFuncScorer)
        assert my_supervised_scorer.get_name() == "my_supervised_scorer"

    def test_decorator_scorer_works(self) -> None:
        @supervised_scorer
        def exact_match(
            inputs: dict[str, Any], expected: Any, output: Any  # noqa: ANN401
        ) -> bool:
            return expected == output

        result = exact_match.score({}, "hello", "hello")
        assert result is True

        result = exact_match.score({}, "hello", "world")
        assert result is False

    def test_decorator_with_float_return(self) -> None:
        @supervised_scorer
        def overlap_score(
            inputs: dict[str, Any], expected: Any, output: Any  # noqa: ANN401
        ) -> float:
            expected_words = set(expected.split())
            output_words = set(output.split())
            if not expected_words:
                return 0.0
            return len(expected_words & output_words) / len(expected_words)

        result = overlap_score.score({}, "the quick brown fox", "the lazy brown dog")
        assert result == 0.5

    def test_decorator_with_lambda_uses_lambda_name(self) -> None:
        scorer = supervised_scorer(lambda inputs, expected, output: expected == output)
        assert scorer.get_name() == "<lambda>"


class TestBaseScorerAbstract:
    def test_cannot_instantiate_base_scorer(self) -> None:
        with pytest.raises(TypeError):
            BaseScorer()

    def test_cannot_instantiate_unsupervised_scorer_without_score(self) -> None:
        class IncompleteScorer(UnsupervisedScorer):
            def get_name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteScorer()

    def test_cannot_instantiate_supervised_scorer_without_score(self) -> None:
        class IncompleteScorer(SupervisedScorer):
            def get_name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteScorer()
