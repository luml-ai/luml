import asyncio
import json
from typing import Any

import pytest

from promptopt.dataclasses import Example, Field, LLMExample
from promptopt.graph import Graph
from promptopt.llm import LLM, InvalidLLMResponseError
from promptopt.nodes.gate import Gate
from promptopt.nodes.io import InputNode, OutputNode
from promptopt.nodes.processor import Processor
from promptopt.optimizers._base import BaseOptimizer
from promptopt.optimizers._eval import BaseMetric, ExactMatch, LLMJudge
from promptopt.optimizers._instruction_proposal import propose_instructions
from promptopt.optimizers._utils import freeze_graph_ids
from promptopt.optimizers.few_shot import RandomFewShotOptimizer
from promptopt.optimizers.jedi import JEDIOptimizer


class DummyLLM(LLM):
    async def generate(self, messages: list, out_schema: Any) -> str:
        return "{}"

    async def batch_generate(
        self,
        messages: list,
        temperature: float = 0.0,
        n_responses: int = 1,
    ) -> list[str]:
        return ["{}" for _ in range(n_responses)]


class DummyOptimizer(BaseOptimizer):
    async def optimize(self, examples: list[Example]) -> None:
        return None


class DummyNode:
    def __init__(self) -> None:
        self.examples: list[Any] = []

    def set_examples(self, examples: list[Any]) -> None:
        self.examples = examples


class TraceGraph:
    def __init__(self, node: DummyNode) -> None:
        self.nodes = {"node": node}
        self.node = node

    async def run(self, inputs: dict[str, Any], llm: LLM, trace: Any = None) -> dict[str, Any]:
        if trace is not None:
            trace.add_example(self.node, str(inputs["id"]), str(inputs["id"]))
        return {"id": inputs["id"]}


class EvalGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Any] = {}

    async def run(self, inputs: dict[str, Any], llm: LLM, trace: Any = None) -> dict[str, Any]:
        return {"prediction": inputs["value"] * 10}


class RecordingMetric(BaseMetric):
    def __init__(self) -> None:
        self.predictions: list[dict[str, Any]] | None = None
        self.targets: list[dict[str, Any]] | None = None

    async def score(
        self, predictions: list[dict], targets: list[dict], **kwargs
    ) -> float:
        self.predictions = predictions
        self.targets = targets
        return 1.0


def test_base_optimizer_sets_graph_attribute() -> None:
    graph = object()
    optimizer = DummyOptimizer(graph=graph)  # type: ignore[arg-type]
    assert optimizer.graph is graph


def test_exact_match_metric_is_awaitable() -> None:
    score = asyncio.run(ExactMatch().score([{"x": 1}], [{"x": 1}]))
    assert score == 1.0


def test_random_few_shot_limits_examples_per_node() -> None:
    node = DummyNode()
    graph = TraceGraph(node=node)
    optimizer = RandomFewShotOptimizer(
        graph=graph,  # type: ignore[arg-type]
        max_training_examples=20,
        max_examples_per_node=2,
        llm=DummyLLM(),
    )

    examples = [
        Example(input={"id": idx}, output={"id": idx})
        for idx in range(6)
    ]

    asyncio.run(optimizer.optimize(examples))

    assert len(node.examples) == 2


def test_jedi_evaluate_passes_predictions_before_targets() -> None:
    metric = RecordingMetric()
    graph = EvalGraph()
    optimizer = JEDIOptimizer(
        graph=graph,  # type: ignore[arg-type]
        student=DummyLLM(),
        teacher=DummyLLM(),
        metrics=[metric],
    )

    val = [
        Example(input={"value": 2}, output={"target": 4}),
        Example(input={"value": 3}, output={"target": 6}),
    ]

    score = asyncio.run(optimizer._evaluate(val=val, graph=graph))  # type: ignore[arg-type]

    assert score == 1.0
    assert metric.predictions == [{"prediction": 20}, {"prediction": 30}]
    assert metric.targets == [{"target": 4}, {"target": 6}]


def processor_graph() -> tuple[Graph, Processor]:
    graph = Graph()
    entry = InputNode([Field("text", "str")])
    processor = Processor([Field("text", "str")], [Field("summary", "str")])
    exit_node = OutputNode([Field("summary", "str")])
    graph.add_node(entry, "input")
    graph.add_node(processor, "summarizer")
    graph.add_node(exit_node, "output")
    graph.connect(entry, "text", processor, "text")
    graph.connect(processor, "summary", exit_node, "summary")
    return graph, processor


def test_instruction_proposals_use_graph_names_and_keep_internal_keys() -> None:
    graph, processor = processor_graph()
    gate = Gate(Field("text", "str"), ["yes", "no"])
    graph.add_node(gate)
    prompts = []

    class CapturingLLM(DummyLLM):
        async def batch_generate(self, messages, temperature=0.0, n_responses=1):
            prompts.append(messages[0]["content"])
            return ["instruction"] * n_responses

    proposals = asyncio.run(propose_instructions(graph, CapturingLLM(), 2))

    assert proposals == {
        id(processor): ["instruction"] * 2,
        id(gate): ["instruction"] * 2,
    }
    for prompt, name in zip(prompts, ["summarizer", "gate_3"]):
        assert graph.llm_repr() in prompt
        assert f"You are generating the instruction for node {name}." in prompt


class PartiallyMalformedLLM(DummyLLM):
    async def generate(self, messages: list, out_schema: Any) -> str:
        if json.loads(messages[-1]["content"])["text"] == "bad":
            return "Sure! Here is the JSON: {}"
        return '{"summary": "valid"}'


@pytest.mark.parametrize("texts", [["bad", "good"], ["bad", "bad"]])
def test_jedi_collect_examples_skips_exhausted_responses(texts: list[str]) -> None:
    graph, node = processor_graph()
    llm = PartiallyMalformedLLM()
    examples = [
        Example(input={"text": text}, output={"summary": "valid"}) for text in texts
    ]
    optimizer = JEDIOptimizer(graph, llm, llm, [ExactMatch()])

    trace = asyncio.run(optimizer._collect_examples(examples))

    assert [example.output for example in trace._examples.get(id(node), [])] == [
        '{"summary": "valid"}'
    ] * texts.count("good")


def test_few_shot_skips_exhausted_responses() -> None:
    graph, node = processor_graph()
    llm = PartiallyMalformedLLM()
    examples = [
        Example(input={"text": text}, output={"summary": "valid"})
        for text in ["bad", "good"]
    ]

    asyncio.run(RandomFewShotOptimizer(graph, 10, 2, llm).optimize(examples))

    assert [example.output for example in node._examples] == ['{"summary": "valid"}']


def test_few_shot_raises_when_every_example_is_exhausted() -> None:
    graph, node = processor_graph()
    original = [LLMExample('{"text": "original"}', '{"summary": "original"}')]
    node.set_examples(original)
    llm = PartiallyMalformedLLM()
    examples = [
        Example(input={"text": "bad"}, output={"summary": "valid"}) for _ in range(2)
    ]

    with pytest.raises(InvalidLLMResponseError, match="any training example"):
        asyncio.run(RandomFewShotOptimizer(graph, 10, 2, llm).optimize(examples))

    assert node._examples == original


def test_few_shot_without_examples_keeps_the_graph() -> None:
    graph, node = processor_graph()
    original = [LLMExample('{"text": "original"}', '{"summary": "original"}')]
    node.set_examples(original)

    asyncio.run(RandomFewShotOptimizer(graph, 10, 2, DummyLLM()).optimize([]))

    assert node._examples == original


@pytest.mark.parametrize("optimizer_kind", ["few_shot", "jedi"])
def test_collect_examples_raises_unrelated_errors_without_waiting_for_other_rows(
    optimizer_kind: str,
) -> None:
    class FailsThenHangsLLM(DummyLLM):
        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, messages: list, out_schema: Any) -> str:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("provider unavailable")
            await asyncio.Event().wait()
            return "{}"

    graph, _ = processor_graph()
    llm = FailsThenHangsLLM()
    examples = [Example(input={"text": str(row)}, output={}) for row in range(3)]
    if optimizer_kind == "few_shot":
        optimizer = RandomFewShotOptimizer(graph, 10, 2, llm)
        operation = optimizer.optimize(examples)
    else:
        optimizer = JEDIOptimizer(graph, llm, llm, [ExactMatch()])
        operation = optimizer._collect_examples(examples)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(asyncio.wait_for(operation, timeout=1))


@pytest.mark.parametrize(
    "scores", [[0.0, 0.0, 0.0], [-3.0, -1.0, -2.0], [0.0, 0.5, 0.25]]
)
def test_jedi_applies_best_trial_including_nonpositive_scores(scores: list[float]) -> None:
    graph, node = processor_graph()
    freeze_graph_ids(graph)
    optimizer = JEDIOptimizer(graph, DummyLLM(), DummyLLM(), [ExactMatch()], n_trials=3)
    evaluated = []

    async def evaluate(val, graph):
        candidate = graph.nodes["summarizer"]
        evaluated.append((candidate._instruction, candidate._examples))
        return scores[len(evaluated) - 1]

    optimizer._evaluate = evaluate
    demos = [[LLMExample("input-a", "output-a")], [LLMExample("input-b", "output-b")]]

    asyncio.run(
        optimizer._optimize_optuna(
            [], {id(node): ["INSTR-A", "INSTR-B"]}, {id(node): demos}
        )
    )

    assert (node._instruction, node._examples) == evaluated[scores.index(max(scores))]
    assert node._instruction is not None
    assert node._examples is not None


class TrialLLM(DummyLLM):
    def __init__(self, malformed_calls: float) -> None:
        self.calls = 0
        self.malformed_calls = malformed_calls

    async def generate(self, messages: list, out_schema: Any) -> str:
        self.calls += 1
        if self.calls <= self.malformed_calls:
            return "malformed"
        return '{"summary": "valid"}'


def test_jedi_continues_after_malformed_trial() -> None:
    graph, node = processor_graph()
    freeze_graph_ids(graph)
    node.set_instruction("original")
    llm = TrialLLM(malformed_calls=3)
    optimizer = JEDIOptimizer(graph, llm, llm, [ExactMatch()], n_trials=2)
    val = [Example(input={"text": "example"}, output={"summary": "valid"})]

    asyncio.run(optimizer._optimize_optuna(val, {id(node): ["candidate"]}, {}))

    assert node._instruction == "candidate"
    assert llm.calls == 4


def test_jedi_raises_when_no_trial_completes() -> None:
    graph, node = processor_graph()
    freeze_graph_ids(graph)
    node.set_instruction("original")
    llm = TrialLLM(malformed_calls=float("inf"))
    optimizer = JEDIOptimizer(graph, llm, llm, [ExactMatch()], n_trials=2)
    val = [Example(input={"text": "example"}, output={"summary": "valid"})]

    with pytest.raises(InvalidLLMResponseError, match="any trial"):
        asyncio.run(optimizer._optimize_optuna(val, {id(node): ["candidate"]}, {}))

    assert node._instruction == "original"
    assert llm.calls == 6


def test_jedi_raises_when_the_judge_never_returns_a_valid_score() -> None:
    class BrokenJudge(DummyLLM):
        async def generate(self, messages: list, out_schema: Any) -> str:
            return "malformed"

    graph, node = processor_graph()
    freeze_graph_ids(graph)
    node.set_instruction("original")
    optimizer = JEDIOptimizer(
        graph,
        TrialLLM(malformed_calls=0),
        BrokenJudge(),
        [LLMJudge("accuracy")],
        n_trials=2,
    )
    val = [Example(input={"text": "example"}, output={"summary": "valid"})]

    with pytest.raises(InvalidLLMResponseError, match="any trial"):
        asyncio.run(optimizer._optimize_optuna(val, {id(node): ["candidate"]}, {}))

    assert node._instruction == "original"


def row(text: str) -> Example:
    return Example(input={"text": text}, output={"summary": "valid"})


def test_jedi_evaluate_scores_exhausted_rows_as_empty_predictions() -> None:
    graph, _ = processor_graph()
    llm = PartiallyMalformedLLM()
    metric = RecordingMetric()
    val = [row("bad"), row("good")]

    exact = JEDIOptimizer(graph, llm, llm, [ExactMatch()])
    score = asyncio.run(exact._evaluate(val, graph))
    recording = JEDIOptimizer(graph, llm, llm, [metric])
    asyncio.run(recording._evaluate(val, graph))

    assert score == 0.5
    assert metric.predictions == [{}, {"summary": "valid"}]


def test_jedi_evaluate_raises_when_every_row_is_exhausted() -> None:
    graph, _ = processor_graph()
    llm = PartiallyMalformedLLM()
    optimizer = JEDIOptimizer(graph, llm, llm, [ExactMatch()])

    with pytest.raises(InvalidLLMResponseError, match="any validation example"):
        asyncio.run(optimizer._evaluate([row("bad"), row("bad")], graph))


def test_jedi_applies_candidate_despite_persistently_malformed_row() -> None:
    graph, node = processor_graph()
    freeze_graph_ids(graph)
    node.set_instruction("original")
    llm = PartiallyMalformedLLM()
    optimizer = JEDIOptimizer(graph, llm, llm, [ExactMatch()], n_trials=2)

    asyncio.run(
        optimizer._optimize_optuna(
            [row("bad"), row("good")], {id(node): ["candidate"]}, {}
        )
    )

    assert node._instruction == "candidate"
