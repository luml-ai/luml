import asyncio
from typing import Any

from promptopt.dataclasses import Example
from promptopt.llm import LLM
from promptopt.optimizers._base import BaseOptimizer
from promptopt.optimizers._eval import BaseMetric, ExactMatch
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
