import asyncio
from typing import Any

import pytest

from promptopt.dataclasses import Field, Socket, StateDescriptor
from promptopt.llm import LLM
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
