from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from luml.llm._exceptions import LLMError


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM clients. Any object with this method signature works."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to an LLM and return the raw text response."""
        ...


class OpenAIClient:
    """LLM client backed by the OpenAI chat-completions API.

    Works with any OpenAI-compatible endpoint. Requires the ``openai`` package
    (install via ``pip install luml_sdk[llm]``).

    >>> from luml.llm import OpenAIClient
    >>> client = OpenAIClient(model="gpt-4.1-mini", temperature=0.0)
    >>> client = OpenAIClient(base_url="http://localhost:8080/v1")
    """

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        max_retries: int = 2,
    ) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install it with: pip install luml_sdk[llm]  — or provide "
                "a custom LLMClient implementation."
            ) from exc

        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._response_format = response_format
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=max_retries,
        )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
        }
        if self._response_format is not None:
            kwargs["response_format"] = self._response_format
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(str(exc)) from exc

        return response.choices[0].message.content or ""
