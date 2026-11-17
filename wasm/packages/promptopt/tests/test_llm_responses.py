import asyncio
import json
from typing import Any

import pytest

from promptopt.dataclasses import Field, Socket, StateDescriptor
from promptopt.llm import (
    LLM,
    InvalidLLMResponseError,
    OllamaProvider,
    OpenAIProvider,
)
from promptopt.nodes.gate import Gate
from promptopt.nodes.processor import Processor
from promptopt.optimizers._eval import LLMJudge
from promptopt.trace import Trace


class SequenceLLM(LLM):
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    async def generate(self, messages: list, out_schema: Any) -> str:
        self.calls += 1
        return next(self.responses)

    async def batch_generate(
        self, messages: list, temperature: float = 0.0, n_responses: int = 1
    ) -> list[str]:
        return ["instruction"] * n_responses


@pytest.mark.parametrize("kind", ["processor", "gate"])
@pytest.mark.parametrize(
    "malformed",
    [
        'Sure! Here is the JSON: {"classification": "yes"}',
        "{",
        "null",
        "[]",
        "{}",
        '{"classification": 1}',
        '{"classification": "yes", "extra": true}',
        '{"classification": "unknown"}',
    ],
)
def test_nodes_retry_malformed_responses_without_tracing_them(
    kind: str, malformed: str
) -> None:
    if kind == "processor":
        node = Processor(
            [Field("text", "str")],
            [Field("classification", "str", allowed_values=["yes", "no"])],
        )
    else:
        node = Gate(Field("text", "str"), ["yes", "no"])
    socket = Socket("destination")
    state = StateDescriptor("destination", "str")
    node.add_output_connection(
        "classification" if kind == "processor" else "yes", [socket], [state]
    )
    valid = '{"classification": "yes"}'
    llm = SequenceLLM([malformed, valid])
    trace = Trace()

    result = asyncio.run(node.generate({"text": "example"}, llm, trace))

    assert llm.calls == 2
    assert result.writes == {state: "yes" if kind == "processor" else "example"}
    assert result.triggers == [socket]
    assert [example.output for example in trace._examples[id(node)]] == [valid]


@pytest.mark.parametrize("kind", ["processor", "gate"])
def test_nodes_bound_retries_and_do_not_trace_exhausted_responses(kind: str) -> None:
    if kind == "processor":
        node = Processor([Field("text", "str")], [Field("result", "str")])
    else:
        node = Gate(Field("text", "str"), ["yes", "no"])
    llm = SequenceLLM(["malformed"] * 3)
    trace = Trace()

    with pytest.raises(ValueError, match="valid structured response"):
        asyncio.run(node.generate({"text": "example"}, llm, trace))

    assert llm.calls == 3
    assert trace._examples == {}


def test_llm_judge_retries_malformed_scores() -> None:
    llm = SequenceLLM(["malformed", '{"score": 4}'])

    score = asyncio.run(LLMJudge("accuracy").score([{}], [{}], llm=llm))

    assert score == 4
    assert llm.calls == 2


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_llm_judge_accepts_scores_in_range(score: int) -> None:
    llm = SequenceLLM([json.dumps({"score": score})])

    result = asyncio.run(LLMJudge("accuracy").score([{}], [{}], llm=llm))

    assert result == score
    assert llm.calls == 1


@pytest.mark.parametrize("provider_kind", ["openai", "ollama"])
@pytest.mark.parametrize("score", [100, 0, -5])
def test_llm_judge_providers_constrain_and_retry_out_of_range_scores(
    provider_kind: str, score: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    if provider_kind == "openai":
        llm = OpenAIProvider(api_key="test-key")
    else:
        llm = OllamaProvider()
    responses = iter([json.dumps({"score": score}), '{"score": 4}'])
    schemas = []

    async def chat(*, response_format, **kwargs):
        if provider_kind == "openai":
            assert response_format["type"] == "json_schema"
            assert response_format["json_schema"]["strict"] is True
            schemas.append(response_format["json_schema"]["schema"])
            return {"choices": [{"message": {"content": next(responses)}}]}
        schemas.append(response_format)
        return {"message": {"content": next(responses)}}

    monkeypatch.setattr(llm, "chat", chat)

    result = asyncio.run(LLMJudge("accuracy").score([{}], [{}], llm=llm))

    assert result == 4
    assert len(schemas) == 2
    for schema in schemas:
        assert schema["properties"]["score"] == {
            "type": "integer",
            "enum": [1, 2, 3, 4, 5],
        }


@pytest.mark.parametrize("score", [100, 0, -5, True, 2.5, "4", None])
def test_llm_judge_rejects_invalid_scores_after_three_attempts(score: Any) -> None:
    llm = SequenceLLM([json.dumps({"score": score})] * 3)

    with pytest.raises(InvalidLLMResponseError, match="after 3 attempts"):
        asyncio.run(LLMJudge("accuracy").score([{}], [{}], llm=llm))

    assert llm.calls == 3


def test_llm_judge_averages_only_valid_scores() -> None:
    llm = SequenceLLM(
        ['{"score": 1}', '{"score": 1}', '{"score": 100}', '{"score": 2}']
    )

    result = asyncio.run(LLMJudge("accuracy").score([{}] * 3, [{}] * 3, llm=llm))

    assert result == pytest.approx(4 / 3)
    assert llm.calls == 4
