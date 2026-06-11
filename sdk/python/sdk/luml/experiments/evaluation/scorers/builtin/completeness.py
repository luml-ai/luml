from typing import Any

from luml.experiments.evaluation.scorers.builtin._base import (
    LLMJudgeScorer,
    _extract_input,
)
from luml.experiments.evaluation.scorers.builtin._prompts import JSON_OUTPUT_INSTRUCTION
from luml.llm import LLMClient

_DEFAULT_KEYS = ("question", "task")

_SYSTEM_PROMPT = (
    "You evaluate whether a response fully and completely addresses all parts "
    "of a question or task. Score from 0.0 to 1.0 where 0.0 means the "
    "response does not address the question/task, 0.5 means it addresses some "
    "parts but leaves important parts unanswered, and 1.0 means it fully and "
    "completely addresses all parts. First reason, then assign a score. "
    f"{JSON_OUTPUT_INSTRUCTION}"
)


class Completeness(LLMJudgeScorer):
    """Scores whether a response fully addresses all parts of a question or task.

    Unsupervised scorer — no expected output required. Returns a float 0.0
    (does not address the question) to 1.0 (fully and completely addresses
    all parts).

    Default input keys: ``"question"``, ``"task"``.

    >>> from luml.experiments.evaluation.scorers.builtin import Completeness
    >>> scorer = Completeness()
    """
    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(client=client, input_key=input_key, name=name)

    def default_name(self) -> str:
        return "completeness"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        question = _extract_input(inputs, self._input_key, _DEFAULT_KEYS)
        user_prompt = f"Question / task:\n{question}\n\nResponse:\n{str(output)}"
        return (_SYSTEM_PROMPT, user_prompt)
