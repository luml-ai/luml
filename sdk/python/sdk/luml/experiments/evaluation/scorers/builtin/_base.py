import json
import re
from abc import abstractmethod
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from luml.experiments.evaluation.scorers.base import (
    BaseScorer,
    SupervisedScorer,
    UnsupervisedScorer,
)
from luml.experiments.evaluation.scorers.builtin._exceptions import (
    JudgeModelError,
    MissingExpectedOutputError,
)
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


def _require_expected_output(scorer_name: str, expected_output: Any) -> None:  # noqa: ANN401
    """Fail fast when a supervised scorer is given no reference to compare against.

    Treats ``None`` and empty containers/strings as "missing" — a supervised
    scorer has nothing to score against in those cases.
    """
    is_empty = expected_output is None or (
        isinstance(expected_output, str | list | tuple | set | dict)
        and len(expected_output) == 0
    )
    if is_empty:
        raise MissingExpectedOutputError(
            f"Supervised scorer '{scorer_name}' requires a non-empty "
            f"expected_output, but received {expected_output!r}."
        )


def _client_model(client: LLMClient) -> str | None:
    """Best-effort judge model identifier.

    The ``LLMClient`` protocol does not require exposing the model, so we
    probe the common attributes (``OpenAIClient`` stores it on ``_model``).
    """
    model = getattr(client, "_model", None) or getattr(client, "model", None)
    return str(model) if model else None


_NAME_PART_SANITIZER = re.compile(r"[^0-9A-Za-z._-]+")


def _input_key_label(input_key: str | tuple[str, ...] | None) -> str | None:
    """Render an ``input_key`` as a single suffix fragment (``None`` if unset)."""
    if isinstance(input_key, str):
        return input_key
    keys = tuple(input_key or ())
    return "_".join(keys) if keys else None


def _disambiguate_scorer_names(scorers: list[BaseScorer]) -> None:
    """Rename auto-named builtin scorers that would otherwise collide on a name.

    Only scorers that actually share a name are touched; anything already
    uniquely named is left exactly as-is. For a colliding group, only the
    dimensions that differ across it are appended as a suffix — a differing
    ``input_key`` and/or a differing judge model. Dimensions identical across
    the group are not used. Examples::

        [Relevancy(client=a), Relevancy(client=b)]
            -> "relevancy_gpt-4.1-mini", "relevancy_gpt-4o-mini"
        [Relevancy(input_key="prompt"), Relevancy(input_key="question")]
            -> "relevancy_prompt", "relevancy_question"
        [Relevancy(input_key="q", client=a), Relevancy(input_key="q", client=b)]
            -> "relevancy_gpt-4.1-mini", "relevancy_gpt-4o-mini"

    Scorers given an explicit ``name``, lone scorers, and non-builtin scorers
    are never modified. The operation is idempotent.
    """
    groups: dict[str, list[Any]] = {}
    for scorer in scorers:
        if not getattr(scorer, "_name_is_default", False):
            continue
        if not (hasattr(scorer, "_input_key") and hasattr(scorer, "_client")):
            continue
        groups.setdefault(scorer.default_name(), []).append(scorer)  # type: ignore[attr-defined]

    for base, group in groups.items():
        if len(group) < 2:
            continue  # no collision — leave it untouched

        dims = [
            (_input_key_label(s._input_key), _client_model(s._client))
            for s in group
        ]
        use_key = len({key for key, _ in dims}) > 1
        use_model = len({model for _, model in dims}) > 1
        for scorer, (key_label, model) in zip(group, dims, strict=True):
            parts = [base]
            if use_key and key_label:
                parts.append(_NAME_PART_SANITIZER.sub("_", key_label))
            if use_model and model:
                parts.append(_NAME_PART_SANITIZER.sub("_", model))
            scorer._name = "_".join(parts)


def _run_traced_judge(
    scorer: BaseScorer,
    client: LLMClient,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    name = scorer.get_name()
    with _tracer.start_as_current_span("llm_judge") as span:
        span.set_attribute("eval.scorer.name", name)
        model = _client_model(client)
        if model:
            span.set_attribute("eval.scorer.model", model)
        judgment = _call_judge(client, system_prompt, user_prompt)
        result = scorer.parse_judgment(judgment)  # type: ignore[attr-defined]
        score_value = result.get(name)
        if isinstance(score_value, int | float) and not isinstance(score_value, bool):
            span.set_attribute("eval.scorer.score", float(score_value))
        reasoning = result.get(f"{name}{REASONING_SUFFIX}")          # <-- add
        if isinstance(reasoning, str) and reasoning:                 # <-- add
            span.set_attribute("eval.scorer.reasoning", reasoning)
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
        self._name_is_default = name is None

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
        self._name_is_default = name is None

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
        _require_expected_output(self.get_name(), expected_output)
        system_prompt, user_prompt = self.build_prompt(inputs, expected_output, output)
        return _run_traced_judge(self, self._client, system_prompt, user_prompt)

    def get_name(self) -> str:
        return self._name
