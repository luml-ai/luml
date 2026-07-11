import json
from typing import Any
from unittest.mock import MagicMock, patch

from luml.experiments.evaluation.scorers.builtin.completeness import Completeness
from luml.llm import LLMClient


def _mock_client(response: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps(response)
    return client


class TestCompletenessInputKeyExtraction:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_question_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "fully addresses", "score": 0.9})
        scorer = Completeness(client=client)
        result = scorer.score(
            {"question": "What is RAG and its benefits?"}, "RAG is ..."
        )
        assert result["completeness"] == 0.9
        user_prompt = client.complete.call_args[0][1]
        assert "What is RAG and its benefits?" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_task_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.7})
        scorer = Completeness(client=client)
        result = scorer.score({"task": "Summarize the article"}, "Summary here")
        assert result["completeness"] == 0.7
        user_prompt = client.complete.call_args[0][1]
        assert "Summarize the article" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_question_preferred_over_task(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.8})
        scorer = Completeness(client=client)
        scorer.score({"question": "Q1", "task": "T1"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Q1" in user_prompt
        assert "T1" not in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_fallback_to_str_inputs(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Completeness(client=client)
        inputs = {"foo": "bar"}
        scorer.score(inputs, "output")
        user_prompt = client.complete.call_args[0][1]
        assert str(inputs) in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_input_key_override(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.6})
        scorer = Completeness(client=client, input_key="prompt")
        scorer.score({"prompt": "Custom prompt", "question": "Q"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Custom prompt" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_input_key_override_missing_falls_to_defaults(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.6})
        scorer = Completeness(client=client, input_key="prompt")
        scorer.score({"question": "Q"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Q" in user_prompt


class TestCompletenessOutputDict:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_has_score_and_reasoning(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "Addresses all parts", "score": 0.85})
        scorer = Completeness(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["completeness"] == 0.85
        assert result["completeness_reasoning"] == "Addresses all parts"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_above(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "max", "score": 1.5})
        scorer = Completeness(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["completeness"] == 1.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_below(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "min", "score": -0.3})
        scorer = Completeness(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["completeness"] == 0.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_missing_reasoning_defaults_to_empty(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"score": 0.8})
        scorer = Completeness(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["completeness_reasoning"] == ""


class TestCompletenessPromptContent:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_system_prompt_contains_json_instruction(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Completeness(client=client)
        scorer.score({"question": "Q"}, "A")
        system_prompt = client.complete.call_args[0][0]
        assert "JSON" in system_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_user_prompt_format(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Completeness(client=client)
        scorer.score({"question": "What is X?"}, "X is Y.")
        user_prompt = client.complete.call_args[0][1]
        assert user_prompt == "Question / task:\nWhat is X?\n\nResponse:\nX is Y."

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_coerced_to_str(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Completeness(client=client)
        scorer.score({"question": "Q"}, {"answer": "A"})
        user_prompt = client.complete.call_args[0][1]
        assert "{'answer': 'A'}" in user_prompt


class TestCompletenessConfiguration:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_default_name(self, mock_openai: MagicMock) -> None:
        scorer = Completeness()
        assert scorer.get_name() == "completeness"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Completeness(client=client, name="my_completeness")
        assert scorer.get_name() == "my_completeness"
        result = scorer.score({"question": "Q"}, "A")
        assert "my_completeness" in result
        assert "my_completeness_reasoning" in result
