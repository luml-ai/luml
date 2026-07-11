from typing import Sequence
from dfs_webworker.prompt_optimization.jsdata import EvaluationModes
from promptopt.graph import Graph
from promptopt.llm import LLM
from promptopt.dataclasses import Example
from promptopt.optimizers.zero_shot import ZeroShotOptimizer
from promptopt.optimizers.few_shot import RandomFewShotOptimizer
from promptopt.optimizers.jedi import JEDIOptimizer
from promptopt.optimizers._eval import BaseMetric, ExactMatch, LLMJudge


SMALL_SIZE_THRESHOLD = 64


def will_use_jedi_optimizer(
    dataset_size: int, evaluation_mode: EvaluationModes
) -> bool:
    return (
        dataset_size >= SMALL_SIZE_THRESHOLD
        and evaluation_mode != EvaluationModes.none_
    )


async def _optimize_zero_shot(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
) -> None:
    optimizer = ZeroShotOptimizer(
        graph=graph, llm=teacher, task_description=task_description
    )
    await optimizer.optimize(dataset)


async def _optimize_small(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
) -> None:
    optimizer1 = ZeroShotOptimizer(
        graph=graph, llm=teacher, task_description=task_description
    )
    optimizer2 = RandomFewShotOptimizer(
        graph=graph,
        max_training_examples=64,
        max_examples_per_node=8,
        llm=student,
    )
    await optimizer1.optimize(dataset)
    await optimizer2.optimize(dataset)


async def _optimize_large(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
    metrics: Sequence[BaseMetric],
) -> None:
    optimizer = JEDIOptimizer(
        graph=graph,
        student=student,
        teacher=teacher,
        metrics=metrics,
        train_fraction=0.75,
        max_training_examples=256,
        max_examples_per_node=8,
        max_validation_batch_size=64,
        n_instructions_to_propose=2,
        task_description=task_description,
    )
    await optimizer.optimize(dataset)


async def optimize(
    student: LLM,
    teacher: LLM,
    graph: Graph,
    dataset: list[Example],
    task_description: str | None,
    evaluation_mode: EvaluationModes = EvaluationModes.none_,
    criteria_list: list[str] | None = None,
) -> None:
    if len(dataset) < 1 or evaluation_mode == EvaluationModes.none_:
        await _optimize_zero_shot(
            student=student,
            teacher=teacher,
            graph=graph,
            dataset=dataset,
            task_description=task_description,
        )
    elif len(dataset) < SMALL_SIZE_THRESHOLD:
        await _optimize_small(
            student=student,
            teacher=teacher,
            graph=graph,
            dataset=dataset,
            task_description=task_description,
        )
    else:
        if evaluation_mode == EvaluationModes.exact_match:
            metrics = [ExactMatch()]
        else:
            if criteria_list is None or len(criteria_list) == 0:
                raise ValueError(
                    "Evaluation mode is not exact match, but no criteria list provided"
                )
            metrics = [LLMJudge(c) for c in criteria_list]

        await _optimize_large(
            student=student,
            teacher=teacher,
            graph=graph,
            dataset=dataset,
            task_description=task_description,
            metrics=metrics,
        )
