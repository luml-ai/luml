from promptopt.optimizers._base import BaseOptimizer
from promptopt.optimizers._utils import run_examples
from promptopt.dataclasses import Example
from promptopt.graph import Graph
from promptopt.trace import Trace
from promptopt.llm import LLM, InvalidLLMResponseError

import random


class RandomFewShotOptimizer(BaseOptimizer):
    def __init__(
        self,
        graph: Graph,
        max_training_examples: int,
        max_examples_per_node: int,
        llm: LLM,
    ) -> None:
        self.graph = graph
        self.llm = llm

        self.max_training_examples = max_training_examples
        self.max_examples_per_node = max_examples_per_node

    async def optimize(self, examples: list[Example]) -> None:
        if len(examples) > self.max_training_examples:
            training_examples = random.sample(examples, self.max_training_examples)
        else:
            training_examples = examples[:]

        trace = Trace()
        completed = await run_examples(
            self.graph, training_examples, self.llm, trace
        )
        if training_examples and not completed:
            raise InvalidLLMResponseError(
                "Optimization failed: the LLM returned no valid structured response "
                "for any training example."
            )

        for node in self.graph.nodes.values():
            if id(node) in trace._examples:
                node_examples = trace._examples[id(node)][:]
                random.shuffle(node_examples)
                node.set_examples(node_examples[: self.max_examples_per_node])
