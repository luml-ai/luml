from typing import Any

from luml.experiments.evaluation.scorers.builtin._base import (
    LLMJudgeScorer,
    _extract_input,
)
from luml.experiments.evaluation.scorers.builtin._prompts import JSON_OUTPUT_INSTRUCTION
from luml.llm import LLMClient

_DEFAULT_KEYS = ("question", "query")

_SYSTEM_PROMPT = (
    "You are an impartial evaluator. Assess how relevant a response is to a "
    "given question. Score on a continuous scale from 0.0 to 1.0 where 0.0 "
    "means the response is completely irrelevant, 0.5 means it is partially "
    "relevant but misses key aspects or includes irrelevant content, and 1.0 "
    "means it is fully relevant and directly addresses the question. "
    f"First reason about the relevance, then assign a score. {JSON_OUTPUT_INSTRUCTION}"
)


class Relevancy(LLMJudgeScorer):
    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(client=client, input_key=input_key, name=name)

    def default_name(self) -> str:
        return "relevancy"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        question = _extract_input(inputs, self._input_key, _DEFAULT_KEYS)
        user_prompt = f"Question:\n{question}\n\nResponse:\n{str(output)}"
        return (_SYSTEM_PROMPT, user_prompt)
