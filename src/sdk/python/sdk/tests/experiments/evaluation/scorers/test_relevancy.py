import json
from typing import Any
from unittest.mock import MagicMock, patch

from luml.experiments.evaluation.scorers.builtin.relevancy import Relevancy
from luml.llm import LLMClient


def _mock_client(response: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps(response)
    return client


class TestRelevancyInputKeyExtraction:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_question_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "relevant", "score": 0.9})
        scorer = Relevancy(client=client)
        result = scorer.score({"question": "What is RAG?"}, "RAG is ...")
        assert result["relevancy"] == 0.9
        user_prompt = client.complete.call_args[0][1]
        assert "What is RAG?" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_query_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.7})
        scorer = Relevancy(client=client)
        result = scorer.score({"query": "Tell me about RAG"}, "RAG is ...")
        assert result["relevancy"] == 0.7
        user_prompt = client.complete.call_args[0][1]
        assert "Tell me about RAG" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_question_preferred_over_query(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.8})
        scorer = Relevancy(client=client)
        scorer.score({"question": "Q1", "query": "Q2"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Q1" in user_prompt
        assert "Q2" not in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_fallback_to_str_inputs(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Relevancy(client=client)
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
        scorer = Relevancy(client=client, input_key="prompt")
        scorer.score({"prompt": "Custom prompt", "question": "Q"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Custom prompt" in user_prompt
        assert "Question:" in user_prompt  # label is always "Question:"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_input_key_override_missing_falls_to_defaults(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.6})
        scorer = Relevancy(client=client, input_key="prompt")
        scorer.score({"question": "Q"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Q" in user_prompt


class TestRelevancyOutputDict:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_has_score_and_reasoning(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "Directly relevant", "score": 0.85})
        scorer = Relevancy(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["relevancy"] == 0.85
        assert result["relevancy_reasoning"] == "Directly relevant"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_above(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "max", "score": 1.5})
        scorer = Relevancy(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["relevancy"] == 1.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_below(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "min", "score": -0.3})
        scorer = Relevancy(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["relevancy"] == 0.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_missing_reasoning_defaults_to_empty(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"score": 0.8})
        scorer = Relevancy(client=client)
        result = scorer.score({"question": "Q"}, "A")
        assert result["relevancy_reasoning"] == ""


class TestRelevancyPromptContent:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_system_prompt_contains_json_instruction(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Relevancy(client=client)
        scorer.score({"question": "Q"}, "A")
        system_prompt = client.complete.call_args[0][0]
        assert "JSON" in system_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_user_prompt_format(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Relevancy(client=client)
        scorer.score({"question": "What is X?"}, "X is Y.")
        user_prompt = client.complete.call_args[0][1]
        assert user_prompt == "Question:\nWhat is X?\n\nResponse:\nX is Y."

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_coerced_to_str(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Relevancy(client=client)
        scorer.score({"question": "Q"}, {"answer": "A"})
        user_prompt = client.complete.call_args[0][1]
        assert "{'answer': 'A'}" in user_prompt


class TestRelevancyConfiguration:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_default_name(self, mock_openai: MagicMock) -> None:
        scorer = Relevancy()
        assert scorer.get_name() == "relevancy"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name(self, mock_openai: MagicMock) -> None:
        scorer = Relevancy(name="my_relevancy")
        assert scorer.get_name() == "my_relevancy"
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Relevancy(client=client, name="my_relevancy")
        result = scorer.score({"question": "Q"}, "A")
        assert "my_relevancy" in result
        assert "my_relevancy_reasoning" in result
