import json
from typing import Any
from unittest.mock import MagicMock, patch

from luml.experiments.evaluation.scorers.builtin.prompt_alignment import PromptAlignment
from luml.llm import LLMClient


def _mock_client(response: dict[str, Any]) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps(response)
    return client


class TestPromptAlignmentInputKeyExtraction:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_extracts_instructions_key(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "follows all", "score": 0.95})
        scorer = PromptAlignment(client=client)
        result = scorer.score(
            {"instructions": "Use bullet points."}, "- Point 1\n- Point 2"
        )
        assert result["prompt_alignment"] == 0.95
        user_prompt = client.complete.call_args[0][1]
        assert "Use bullet points." in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_fallback_to_str_inputs(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = PromptAlignment(client=client)
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
        scorer = PromptAlignment(client=client, input_key="prompt")
        scorer.score({"prompt": "Be concise", "instructions": "I"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Be concise" in user_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_input_key_override_missing_falls_to_defaults(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.6})
        scorer = PromptAlignment(client=client, input_key="prompt")
        scorer.score({"instructions": "Use formal tone"}, "output")
        user_prompt = client.complete.call_args[0][1]
        assert "Use formal tone" in user_prompt


class TestPromptAlignmentOutputDict:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_has_score_and_reasoning(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "Follows format", "score": 0.9})
        scorer = PromptAlignment(client=client)
        result = scorer.score({"instructions": "I"}, "R")
        assert result["prompt_alignment"] == 0.9
        assert result["prompt_alignment_reasoning"] == "Follows format"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_above(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "max", "score": 1.5})
        scorer = PromptAlignment(client=client)
        result = scorer.score({"instructions": "I"}, "R")
        assert result["prompt_alignment"] == 1.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_score_clamped_below(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "min", "score": -0.3})
        scorer = PromptAlignment(client=client)
        result = scorer.score({"instructions": "I"}, "R")
        assert result["prompt_alignment"] == 0.0

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_missing_reasoning_defaults_to_empty(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"score": 0.8})
        scorer = PromptAlignment(client=client)
        result = scorer.score({"instructions": "I"}, "R")
        assert result["prompt_alignment_reasoning"] == ""


class TestPromptAlignmentPromptContent:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_system_prompt_contains_json_instruction(
        self, mock_openai: MagicMock
    ) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = PromptAlignment(client=client)
        scorer.score({"instructions": "I"}, "R")
        system_prompt = client.complete.call_args[0][0]
        assert "JSON" in system_prompt

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_user_prompt_format(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = PromptAlignment(client=client)
        scorer.score({"instructions": "Be brief."}, "Short answer.")
        user_prompt = client.complete.call_args[0][1]
        assert user_prompt == "Instructions:\nBe brief.\n\nResponse:\nShort answer."

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_output_coerced_to_str(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = PromptAlignment(client=client)
        scorer.score({"instructions": "I"}, {"answer": "A"})
        user_prompt = client.complete.call_args[0][1]
        assert "{'answer': 'A'}" in user_prompt


class TestPromptAlignmentConfiguration:
    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_default_name(self, mock_openai: MagicMock) -> None:
        scorer = PromptAlignment()
        assert scorer.get_name() == "prompt_alignment"

    @patch(
        "luml.experiments.evaluation.scorers.builtin._base.OpenAIClient",
        autospec=True,
    )
    def test_custom_name(self, mock_openai: MagicMock) -> None:
        client = _mock_client({"reasoning": "ok", "score": 0.5})
        scorer = PromptAlignment(client=client, name="my_alignment")
        assert scorer.get_name() == "my_alignment"
        result = scorer.score({"instructions": "I"}, "R")
        assert "my_alignment" in result
        assert "my_alignment_reasoning" in result
