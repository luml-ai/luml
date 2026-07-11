from promptopt.optimizers._base import BaseOptimizer
from promptopt.dataclasses import Example
from promptopt.graph import Graph
from promptopt.trace import Trace
from promptopt.llm import LLM
import random


def split_dataset(
    examples: list[Example], train_fraction: float = 0.75
) -> tuple[list[Example], list[Example]]:
    random.shuffle(examples)
    split_index = int(len(examples) * train_fraction)
    train_set = examples[:split_index]
    test_set = examples[split_index:]
    return train_set, test_set


def freeze_graph_ids(graph: Graph) -> None:
    for node in graph.nodes.values():
        node._frozen_id = id(node)
