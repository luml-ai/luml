from typing import Any

from luml.experiments.evaluation.scorers.builtin._base import (
    LLMJudgeScorer,
    _extract_input,
)
from luml.experiments.evaluation.scorers.builtin._prompts import JSON_OUTPUT_INSTRUCTION
from luml.llm import LLMClient

_DEFAULT_KEYS = ("text",)

_SYSTEM_PROMPT = (
    "You evaluate the quality of a summary against its source text. A good "
    "summary accurately captures the key information from the source without "
    "adding false or unsupported information (no hallucination) and without "
    "omitting essential points. Score from 0.0 to 1.0 where 0.0 means the "
    "summary is inaccurate, misleading, or fabricates information; 0.5 means "
    "it is accurate but misses important information or contains minor "
    "inaccuracies; and 1.0 means it accurately and concisely captures all key "
    "information from the source. First reason, then assign a score. "
    f"{JSON_OUTPUT_INSTRUCTION}"
)


class Summarization(LLMJudgeScorer):
    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(client=client, input_key=input_key, name=name)

    def default_name(self) -> str:
        return "summarization"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        text = _extract_input(inputs, self._input_key, _DEFAULT_KEYS)
        user_prompt = f"Source text:\n{text}\n\nSummary:\n{str(output)}"
        return (_SYSTEM_PROMPT, user_prompt)
