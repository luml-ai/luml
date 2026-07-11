from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from luml.llm import LLMClient, LLMError, OpenAIClient


class _StubClient:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return "stub"


def _make_completion(content: str | None = "hello") -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


class TestLLMClientProtocol:
    def test_custom_object_satisfies_protocol(self) -> None:
        assert isinstance(_StubClient(), LLMClient)

    def test_object_without_complete_does_not_satisfy(self) -> None:
        assert not isinstance(object(), LLMClient)


class TestOpenAIClientInit:
    def test_import_error_when_openai_missing(self) -> None:
        with (
            patch.dict("sys.modules", {"openai": None}),
            pytest.raises(ImportError, match="luml_sdk\\[llm\\]"),
        ):
            OpenAIClient()

    def test_defaults_forwarded(self) -> None:
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = OpenAIClient()

        mock_openai.OpenAI.assert_called_once_with(
            api_key=None, base_url=None, max_retries=2
        )
        assert client._model == "gpt-4.1-mini"
        assert client._temperature == 0.0
        assert client._max_tokens is None
        assert client._response_format is None

    def test_custom_params_forwarded(self) -> None:
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            client = OpenAIClient(
                model="gpt-4o",
                api_key="sk-test",
                base_url="http://localhost:11434/v1",
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=1024,
                max_retries=5,
            )

        mock_openai.OpenAI.assert_called_once_with(
            api_key="sk-test",
            base_url="http://localhost:11434/v1",
            max_retries=5,
        )
        assert client._model == "gpt-4o"
        assert client._temperature == 0.5
        assert client._max_tokens == 1024
        assert client._response_format == {"type": "json_object"}


class TestOpenAIClientComplete:
    def _make_client(  # noqa: ANN003
        self, **kwargs: str | float | int | dict[str, str] | None
    ) -> OpenAIClient:
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            return OpenAIClient(**kwargs)  # type: ignore[arg-type]

    def test_valid_response(self) -> None:
        client = self._make_client()
        client._client.chat.completions.create.return_value = _make_completion(  # type: ignore[attr-defined]
            "result"
        )
        result = client.complete("sys", "usr")
        assert result == "result"

        call_kwargs = client._client.chat.completions.create.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["model"] == "gpt-4.1-mini"
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ]
        assert "max_tokens" not in call_kwargs
        assert "response_format" not in call_kwargs

    def test_none_content_returns_empty_string(self) -> None:
        client = self._make_client()
        client._client.chat.completions.create.return_value = _make_completion(None)  # type: ignore[attr-defined]
        assert client.complete("sys", "usr") == ""

    def test_api_error_wrapped_as_llm_error(self) -> None:
        client = self._make_client()
        client._client.chat.completions.create.side_effect = RuntimeError("API down")  # type: ignore[attr-defined]
        with pytest.raises(LLMError, match="API down"):
            client.complete("sys", "usr")

    def test_response_format_forwarded(self) -> None:
        client = self._make_client(response_format={"type": "json_object"})
        client._client.chat.completions.create.return_value = _make_completion("{}")  # type: ignore[attr-defined]
        client.complete("sys", "usr")

        call_kwargs = client._client.chat.completions.create.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_max_tokens_forwarded(self) -> None:
        client = self._make_client(max_tokens=512)
        client._client.chat.completions.create.return_value = _make_completion("ok")  # type: ignore[attr-defined]
        client.complete("sys", "usr")

        call_kwargs = client._client.chat.completions.create.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["max_tokens"] == 512

    def test_temperature_override(self) -> None:
        client = self._make_client(temperature=0.8)
        client._client.chat.completions.create.return_value = _make_completion("ok")  # type: ignore[attr-defined]
        client.complete("sys", "usr")

        call_kwargs = client._client.chat.completions.create.call_args.kwargs  # type: ignore[attr-defined]
        assert call_kwargs["temperature"] == 0.8
