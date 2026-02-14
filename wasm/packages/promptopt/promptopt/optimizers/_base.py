from promptopt.dataclasses import Example
from promptopt.graph import Graph
from abc import ABC, abstractmethod


class BaseOptimizer(ABC):
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    @abstractmethod
    async def optimize(self, examples: list[Example]) -> None:
        pass
