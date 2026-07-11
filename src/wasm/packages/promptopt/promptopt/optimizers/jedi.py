import asyncio
from typing import Sequence
from promptopt.optimizers._base import BaseOptimizer
from promptopt.dataclasses import Example, LLMExample
from promptopt.graph import Graph
from promptopt.trace import Trace
from promptopt.llm import LLM
from promptopt.optimizers._utils import split_dataset, freeze_graph_ids
from promptopt.optimizers._instruction_proposal import propose_instructions
from promptopt.optimizers._eval import BaseMetric
from copy import deepcopy
import random
import optuna


class JEDIOptimizer(BaseOptimizer):
    "Joint Examples and DIrectives Optimizer"

    def __init__(
        self,
        graph: Graph,
        student: LLM,
        teacher: LLM,
        metrics: Sequence[BaseMetric],
        train_fraction: float = 0.75,
        max_training_examples: int = 256,
        max_examples_per_node: int = 8,
        max_validation_batch_size: int = 64,
        n_instructions_to_propose: int = 2,
        n_demo_sets: int = 8,
        n_trials: int = 5,
        task_description: str | None = None,
    ) -> None:
        if len(metrics) == 0:
            raise ValueError("At least one metric is required for optimization.")

        self.graph = graph
        self.student = student
        self.teacher = teacher
        self.metrics = metrics

        self.train_fraction = train_fraction
        self.max_training_examples = max_training_examples
        self.max_examples_per_node = max_examples_per_node
        self.max_validation_batch_size = max_validation_batch_size
        self.n_instructions_to_propose = n_instructions_to_propose
        self.task_description = task_description
        self.n_demo_sets = n_demo_sets
        self.n_trials = n_trials

    async def _collect_examples(self, training_examples: list[Example]) -> Trace:
        trace = Trace()
        await asyncio.gather(
            *[
                self.graph.run(example.input, self.teacher, trace)
                for example in training_examples
            ]
        )
        return trace

    def _generate_demo_sets(
        self, examples_trace: Trace
    ) -> dict[int, list[list[LLMExample]]]:
        demo_sets = {}
        for node, examples in examples_trace._examples.items():
            demo_sets[node] = []
            for _ in range(self.n_demo_sets):
                random.shuffle(examples)
                demo_set = examples[: self.max_examples_per_node]
                demo_sets[node].append(demo_set)
        return demo_sets

    async def optimize(self, examples: list[Example]) -> None:
        freeze_graph_ids(self.graph)
        train, val = split_dataset(examples, self.train_fraction)
        if len(train) > self.max_training_examples:
            train = random.sample(train, self.max_training_examples)
        examples_trace = await self._collect_examples(train)
        instruction_proposals = await propose_instructions(
            graph=self.graph,
            llm=self.teacher,
            n_instructions=self.n_instructions_to_propose,
            task_description=self.task_description,
        )
        demo_sets = self._generate_demo_sets(examples_trace)

        await self._optimize_optuna(
            val=val,
            instruction_proposals=instruction_proposals,
            demo_sets=demo_sets,
        )

    def _generate_optuna_distributions(
        self,
        demo_sets: dict[int, list[list[LLMExample]]],
        instruction_proposals: dict[int, list[str]],
    ) -> dict:
        distributions = {}
        for node, sets in demo_sets.items():
            distributions[f"{node}:::demo_set"] = (
                optuna.distributions.CategoricalDistribution(list(range(len(sets))))
            )
        for node, instructions in instruction_proposals.items():
            distributions[f"{node}:::instruction"] = (
                optuna.distributions.CategoricalDistribution(instructions)
            )
        return distributions

    def _select_params(
        self,
        graph: Graph,
        params: dict,
        demo_sets: dict[int, list[list[LLMExample]]],
    ) -> None:
        for node in graph.nodes.values():
            node_id = node._frozen_id
            if node_id is None:
                raise ValueError(f"Node {node} has no frozen ID")
            if f"{node_id}:::demo_set" in params:
                demo_set_index = params[f"{node_id}:::demo_set"]
                node.set_examples(demo_sets[node_id][demo_set_index])
            if f"{node_id}:::instruction" in params:
                instruction = params[f"{node_id}:::instruction"]
                node.set_instruction(instruction)

    async def _evaluate(self, val: list[Example], graph: Graph) -> float:
        if len(val) > self.max_validation_batch_size:
            val = random.sample(val, self.max_validation_batch_size)

        predictions = await asyncio.gather(
            *[graph.run(example.input, self.student) for example in val]
        )

        scores = await asyncio.gather(
            *[
                metric.score(predictions, [v.output for v in val], llm=self.teacher)
                for metric in self.metrics
            ]
        )

        return sum(scores) / len(scores)

    async def _optimize_optuna(
        self,
        val: list[Example],
        instruction_proposals: dict[int, list[str]],
        demo_sets: dict[int, list[list[LLMExample]]],
    ) -> None:
        sampler = optuna.samplers.TPESampler(seed=42, multivariate=True)
        study = optuna.create_study(
            sampler=sampler,
            direction="maximize",
        )
        space = self._generate_optuna_distributions(
            demo_sets=demo_sets, instruction_proposals=instruction_proposals
        )
        best_score = 0
        best_params = {}
        for trial_num in range(self.n_trials):
            trial = study.ask(space)
            graph_copy = deepcopy(self.graph)
            self._select_params(
                graph=graph_copy,
                params=trial.params,
                demo_sets=demo_sets,
            )

            score = await self._evaluate(
                val=val,
                graph=graph_copy,
            )

            if score > best_score:
                best_score = score
                best_params = trial.params
            study.tell(trial, score)
        print(f"Best score: {best_score}")
        print(f"Best params: {best_params}")
        self._select_params(
            graph=self.graph,
            params=best_params,
            demo_sets=demo_sets,
        )
