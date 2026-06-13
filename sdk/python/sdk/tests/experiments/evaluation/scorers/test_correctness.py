import json
from typing import Any
from unittest.mock import MagicMock, patch

from luml.experiments.evaluation.evaluate import _call_scorer
from luml.experiments.evaluation.scorers.base import SupervisedScorer
from luml.experiments.evaluation.scorers.builtin.correctness import Correctness
from luml.experiments.evaluation.types import EvalItem
from luml.llm import LLMClient


def _mock_client(response: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps(response)
    return client


class TestCorrectnessExpectedOutputHandling:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_expected_facts_formatted_as_bullets(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "correct", "score": 0.9})
        scorer = Correctness(client=client)
        expected = {"expected_facts": ["fact one", "fact two"]}
        result = scorer.score({"request": "Q"}, expected, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "- fact one" in user_prompt
        assert "- fact two" in user_prompt
        assert result["correctness"] == 0.9

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_plain_string_expected_output(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.8})
        scorer = Correctness(client=client)
        result = scorer.score({"request": "Capital?"}, "Amsterdam", "Amsterdam")
        user_prompt = client.complete.call_args[0][1]
        assert "Amsterdam" in user_prompt
        assert result["correctness"] == 0.8

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_dict_without_expected_facts_uses_str(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.7})
        scorer = Correctness(client=client)
        expected = {"answer": "42"}
        scorer.score({"request": "Q"}, expected, "output")
        user_prompt = client.complete.call_args[0][1]
        assert str(expected) in user_prompt


class TestCorrectnessInputKeyExtraction:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_request_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.9})
        scorer = Correctness(client=client)
        scorer.score({"request": "What is RAG?"}, "facts", "RAG is ...")
        user_prompt = client.complete.call_args[0][1]
        assert "What is RAG?" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_question_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.7})
        scorer = Correctness(client=client)
        scorer.score({"question": "Capital?"}, "Amsterdam", "Amsterdam")
        user_prompt = client.complete.call_args[0][1]
        assert "Capital?" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_request_preferred_over_question(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.8})
        scorer = Correctness(client=client)
        scorer.score({"request": "R1", "question": "Q2"}, "expected", "output")
        user_prompt = client.complete.call_args[0][1]
        assert "R1" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_fallback_to_str_inputs(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Correctness(client=client)
        inputs = {"foo": "bar"}
        scorer.score(inputs, "expected", "output")
        user_prompt = client.complete.call_args[0][1]
        assert str(inputs) in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_input_key_override(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.6})
        scorer = Correctness(client=client, input_key="prompt")
        scorer.score({"prompt": "Custom", "request": "R"}, "expected", "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Custom" in user_prompt


class TestCorrectnessOutputDict:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_has_score_and_reasoning(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "All facts correct", "score": 0.95})
        scorer = Correctness(client=client)
        result = scorer.score({"request": "Q"}, "facts", "A")
        assert result["correctness"] == 0.95
        assert result["correctness_reasoning"] == "All facts correct"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_above(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "max", "score": 1.5})
        scorer = Correctness(client=client)
        result = scorer.score({"request": "Q"}, "facts", "A")
        assert result["correctness"] == 1.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_below(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "min", "score": -0.3})
        scorer = Correctness(client=client)
        result = scorer.score({"request": "Q"}, "facts", "A")
        assert result["correctness"] == 0.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_missing_reasoning_defaults_to_empty(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"score": 0.8})
        scorer = Correctness(client=client)
        result = scorer.score({"request": "Q"}, "facts", "A")
        assert result["correctness_reasoning"] == ""


class TestCorrectnessIsSupervisedScorer:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_isinstance_supervised_scorer(self, mock_openai: MagicMock) -> None:
        scorer = Correctness()
        assert isinstance(scorer, SupervisedScorer)


class TestCorrectnessCallScorerIntegration:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_call_scorer_routes_to_supervised_branch(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "good", "score": 0.85})
        scorer = Correctness(client=client)
        eval_item = EvalItem(
            id="test-1",
            inputs={"request": "What is RAG?"},
            expected_output={
                "expected_facts": [
                    "RAG combines retrieval with generation",
                    "RAG reduces hallucinations",
                ]
            },
        )
        result = _call_scorer(scorer, eval_item, "RAG is great")
        assert "correctness" in result
        assert "correctness_reasoning" in result
        assert result["correctness"] == 0.85


class TestCorrectnessConfiguration:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_default_name(self, mock_openai: MagicMock) -> None:
        scorer = Correctness()
        assert scorer.get_name() == "correctness"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Correctness(client=client, name="my_correctness")
        assert scorer.get_name() == "my_correctness"
        result = scorer.score({"request": "Q"}, "facts", "A")
        assert "my_correctness" in result
        assert "my_correctness_reasoning" in result


class TestCorrectnessPromptContent:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_system_prompt_contains_json_instruction(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Correctness(client=client)
        scorer.score({"request": "Q"}, "facts", "A")
        system_prompt = client.complete.call_args[0][0]
        assert "JSON" in system_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_user_prompt_format(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Correctness(client=client)
        scorer.score({"request": "What is X?"}, "X is Y", "X is Y.")
        user_prompt = client.complete.call_args[0][1]
        expected = (
            "Request:\nWhat is X?\n\n"
            "Expected facts / reference:\nX is Y\n\n"
            "Response:\nX is Y."
        )
        assert user_prompt == expected

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_coerced_to_str(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Correctness(client=client)
        scorer.score({"request": "Q"}, "facts", {"answer": "A"})
        user_prompt = client.complete.call_args[0][1]
        assert "{'answer': 'A'}" in user_prompt
