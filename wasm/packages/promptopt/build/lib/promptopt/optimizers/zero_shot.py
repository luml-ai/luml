from promptopt.optimizers._base import BaseOptimizer
from promptopt.optimizers._instruction_proposal import propose_instructions
from promptopt.dataclasses import Example
from promptopt.graph import Graph
from promptopt.llm import LLM


class ZeroShotOptimizer(BaseOptimizer):
    def __init__(
        self,
        graph: Graph,
        llm: LLM,
        task_description: str | None = None,
    ) -> None:
        self.graph = graph
        self.llm = llm
        self.task_description = task_description

    async def optimize(self, examples: list[Example]) -> None:
        proposals = await propose_instructions(
            self.graph,
            self.llm,
            n_instructions=1,
            task_description=self.task_description,
        )
        for node in self.graph.nodes.values():
            if id(node) in proposals:
                node.set_instruction(proposals[id(node)][0])
