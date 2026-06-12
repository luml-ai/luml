from typing import Any

from luml.experiments.evaluation.scorers.builtin._base import (
    SupervisedLLMJudgeScorer,
    _extract_input,
)
from luml.experiments.evaluation.scorers.builtin._prompts import JSON_OUTPUT_INSTRUCTION
from luml.llm import LLMClient

_DEFAULT_KEYS = ("request", "question")

_SYSTEM_PROMPT = (
    "You are an impartial evaluator assessing the factual correctness of a "
    "response against a set of expected facts / reference answer. Check "
    "faithfulness (are the stated facts correct and supported by the expected "
    "facts?) and hallucination (does the response fabricate information not "
    "supported by the expected facts?). Score from 0.0 to 1.0 where 0.0 means "
    "the response is factually incorrect, contradicts the expected facts, or "
    "hallucinates; 0.5 means it is partially correct (some expected facts "
    "covered, others missing or wrong); and 1.0 means it is fully correct and "
    "faithful to all expected facts with no hallucinations. First reason, then "
    f"assign a score. {JSON_OUTPUT_INSTRUCTION}"
)


def _format_expected(expected_output: Any) -> str:  # noqa: ANN401
    if isinstance(expected_output, dict) and isinstance(
        expected_output.get("expected_facts"), list
    ):
        return "\n".join(f"- {fact}" for fact in expected_output["expected_facts"])
    return str(expected_output)


class Correctness(SupervisedLLMJudgeScorer):
    """Scores factual correctness of a response against expected facts.

    Supervised scorer — requires ``expected_output``. Checks faithfulness
    (facts correct?) and hallucination (fabricated information?). Returns a
    float 0.0 (incorrect / hallucinated) to 1.0 (fully correct and faithful).

    ``expected_output`` can be a string or a dict with an ``"expected_facts"``
    list, which is formatted as a bulleted block for the judge.

    Default input keys: ``"request"``, ``"question"``.

    >>> from luml.experiments.evaluation.scorers.builtin import Correctness
    >>> scorer = Correctness()
    """
    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(client=client, input_key=input_key, name=name)

    def default_name(self) -> str:
        return "correctness"

    def build_prompt(
        self,
        inputs: dict[str, Any],
        expected_output: Any,  # noqa: ANN401
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]:
        request = _extract_input(inputs, self._input_key, _DEFAULT_KEYS)
        expected_str = _format_expected(expected_output)
        user_prompt = (
            f"Request:\n{request}\n\n"
            f"Expected facts / reference:\n{expected_str}\n\n"
            f"Response:\n{str(output)}"
        )
        return (_SYSTEM_PROMPT, user_prompt)
