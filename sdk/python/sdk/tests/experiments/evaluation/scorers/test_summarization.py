import json
from typing import Any
from unittest.mock import MagicMock, patch

from luml.experiments.evaluation.scorers.builtin.summarization import Summarization
from luml.llm import LLMClient


def _mock_client(response: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps(response)
    return client


class TestSummarizationInputKeyExtraction:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_text_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "good summary", "score": 0.9})
        scorer = Summarization(client=client)
        result = scorer.score({"text": "Long source text about RAG."}, "RAG summary.")
        assert result["summarization"] == 0.9
        user_prompt = client.complete.call_args[0][1]
        assert "Long source text about RAG." in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_fallback_to_str_inputs(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Summarization(client=client)
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
        scorer = Summarization(client=client, input_key="document")
        scorer.score({"document": "Doc content", "text": "T"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Doc content" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_input_key_override_missing_falls_to_defaults(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.6})
        scorer = Summarization(client=client, input_key="document")
        scorer.score({"text": "Source text"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Source text" in user_prompt


class TestSummarizationOutputDict:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_has_score_and_reasoning(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "Captures key points", "score": 0.85})
        scorer = Summarization(client=client)
        result = scorer.score({"text": "Source"}, "Summary")
        assert result["summarization"] == 0.85
        assert result["summarization_reasoning"] == "Captures key points"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_above(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "max", "score": 1.5})
        scorer = Summarization(client=client)
        result = scorer.score({"text": "T"}, "S")
        assert result["summarization"] == 1.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_below(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "min", "score": -0.3})
        scorer = Summarization(client=client)
        result = scorer.score({"text": "T"}, "S")
        assert result["summarization"] == 0.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_missing_reasoning_defaults_to_empty(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"score": 0.8})
        scorer = Summarization(client=client)
        result = scorer.score({"text": "T"}, "S")
        assert result["summarization_reasoning"] == ""


class TestSummarizationPromptContent:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_system_prompt_contains_json_instruction(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Summarization(client=client)
        scorer.score({"text": "T"}, "S")
        system_prompt = client.complete.call_args[0][0]
        assert "JSON" in system_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_user_prompt_format(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Summarization(client=client)
        scorer.score({"text": "Full source text."}, "Short summary.")
        user_prompt = client.complete.call_args[0][1]
        expected = "Source text:\nFull source text.\n\nSummary:\nShort summary."
        assert user_prompt == expected

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_coerced_to_str(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Summarization(client=client)
        scorer.score({"text": "T"}, {"summary": "S"})
        user_prompt = client.complete.call_args[0][1]
        assert "{'summary': 'S'}" in user_prompt


class TestSummarizationConfiguration:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_default_name(self, mock_openai: MagicMock) -> None:
        scorer = Summarization()
        assert scorer.get_name() == "summarization"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = Summarization(client=client, name="my_summarization")
        assert scorer.get_name() == "my_summarization"
        result = scorer.score({"text": "T"}, "S")
        assert "my_summarization" in result
        assert "my_summarization_reasoning" in result
