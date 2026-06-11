import json
from abc import abstractmethod
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from luml.experiments.evaluation.scorers.base import (
    BaseScorer,
    SupervisedScorer,
    UnsupervisedScorer,
)
from luml.experiments.evaluation.scorers.builtin._exceptions import JudgeModelError
from luml.experiments.evaluation.scorers.builtin._prompts import CORRECTIVE_REMINDER
from luml.experiments.evaluation.types import REASONING_SUFFIX
from luml.llm import LLMClient, OpenAIClient

_tracer = trace.get_tracer(__name__)


def _try_parse(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if (
        isinstance(parsed, dict)
        and isinstance(parsed.get("score"), int | float)
        and not isinstance(parsed.get("score"), bool)
    ):
        return parsed
    return None


def _call_judge(
    client: LLMClient, system_prompt: str, user_prompt: str
) -> dict[str, Any]:
    raw = client.complete(system_prompt, user_prompt)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    retry_prompt = f"{user_prompt}\n\n{CORRECTIVE_REMINDER}"
    raw = client.complete(system_prompt, retry_prompt)
    parsed = _try_parse(raw)
    if parsed is not None:
        return parsed

    raise JudgeModelError(
        f"Judge did not return valid JSON with a numeric 'score' "
        f"after one retry. Last response: {raw!r}"
    )


def _default_client(client: LLMClient | None) -> LLMClient:
    return client or OpenAIClient(response_format={"type": "json_object"})


def _extract_input(
    inputs: dict[str, Any],
    input_key: str | tuple[str, ...] | None,
    default_keys: tuple[str, ...],
) -> str:
    override_keys = (
        (input_key,) if isinstance(input_key, str) else tuple(input_key or ())
    )

    for key in (*override_keys, *default_keys):
        if key in inputs:
            return str(inputs[key])
    return str(inputs)


def _run_traced_judge(
    scorer: BaseScorer,
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    name = scorer.get_name()
    with _tracer.start_as_current_span("llm_judge") as span:
        span.set_attribute("eval.scorer.name", name)
        judgment = _call_judge(client, system_prompt, user_prompt)
        result = scorer.parse_judgment(judgment)  # type: ignore[attr-defined]
        score_value = result.get(name)
        if isinstance(score_value, int | float) and not isinstance(score_value, bool):
            span.set_attribute("eval.scorer.score", float(score_value))
        span.set_status(Status(StatusCode.OK))
        return result


class LLMJudgeScorer(UnsupervisedScorer):
    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        self._client = _default_client(client)
        self._input_key = input_key
        self._name = name or self.default_name()

    @abstractmethod
    def default_name(self) -> str: ...

    @abstractmethod
    def build_prompt(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]: ...

    def parse_judgment(self, judgment: dict[str, Any]) -> dict[str, Any]:
        name = self.get_name()
        score = max(0.0, min(1.0, float(judgment["score"])))
        reasoning = str(judgment.get("reasoning", ""))
        return {name: score, f"{name}{REASONING_SUFFIX}": reasoning}

    def score(
        self,
        inputs: dict[str, Any],
        output: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        system_prompt, user_prompt = self.build_prompt(inputs, output)
        return _run_traced_judge(self, self._client, system_prompt, user_prompt)

    def get_name(self) -> str:
        return self._name


class SupervisedLLMJudgeScorer(SupervisedScorer):
    def __init__(
        self,
        client: LLMClient | None = None,
        input_key: str | tuple[str, ...] | None = None,
        name: str | None = None,
    ) -> None:
        self._client = _default_client(client)
        self._input_key = input_key
        self._name = name or self.default_name()

    @abstractmethod
    def default_name(self) -> str: ...

    @abstractmethod
    def build_prompt(
        self,
        inputs: dict[str, Any],
        expected_output: Any,  # noqa: ANN401
        output: Any,  # noqa: ANN401
    ) -> tuple[str, str]: ...

    def parse_judgment(self, judgment: dict[str, Any]) -> dict[str, Any]:
        name = self.get_name()
        score = max(0.0, min(1.0, float(judgment["score"])))
        reasoning = str(judgment.get("reasoning", ""))
        return {name: score, f"{name}{REASONING_SUFFIX}": reasoning}

    def score(
        self,
        inputs: dict[str, Any],
        expected_output: Any,  # noqa: ANN401
        output: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        system_prompt, user_prompt = self.build_prompt(inputs, expected_output, output)
        return _run_traced_judge(self, self._client, system_prompt, user_prompt)

    def get_name(self) -> str:
        return self._name
