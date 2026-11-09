from abc import ABC, abstractmethod

from promptopt.dataclasses import Example
from promptopt.graph import Graph


class BaseOptimizer(ABC):
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    @abstractmethod
    async def optimize(self, examples: list[Example]) -> None:
        pass
