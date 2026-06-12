from typing import Any

from luml.experiments.evaluation.scorers.builtin._base import (
    LLMJudgeScorer,
    _extract_input,
)
from luml.experiments.evaluation.scorers.builtin._prompts import JSON_OUTPUT_INSTRUCTION
from luml.llm import LLMClient

_DEFAULT_KEYS = ("instructions",)

_SYSTEM_PROMPT = (
    "You evaluate whether a response follows the given instructions. Consider "
    "all constraints in the instructions (format, length, style, and content "
    "requirements). Score from 0.0 to 1.0 where 0.0 means the response "
    "ignores or violates the instructions, 0.5 means it follows some "
    "instructions but violates others, and 1.0 means it fully follows all "
    f"instructions. First reason, then assign a score. {JSON_OUTPUT_INSTRUCTION}"
)


class PromptAlignment(LLMJudgeScorer):
    """Scores whether a response follows the given instructions.

    Unsupervised scorer — no expected output required. Considers format,
    length, style, and content constraints. Returns a float 0.0 (instructions
    ignored) to 1.0 (all instructions followed).

    Default input keys: ``"instructions"``.

    >>> from luml.experiments.evaluation.scorers.builtin import PromptAlignment
    >>> scorer = PromptAlignment()
    >>> scorer = PromptAlignment(input_key="system_prompt")
    """

    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(client=client, input_key=input_key, name=name)

    def default_name(self) -> str:
        return "prompt_alignment"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        instructions = _extract_input(inputs, self._input_key, _DEFAULT_KEYS)
        user_prompt = f"Instructions:\n{instructions}\n\nResponse:\n{str(output)}"
        return (_SYSTEM_PROMPT, user_prompt)
