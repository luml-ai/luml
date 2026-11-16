import asyncio
from dataclasses import dataclass

from promptopt.graph import Graph
from promptopt.llm import LLM, InvalidLLMResponseError

from dfs_webworker.prompt_optimization.jsdata import JsData
from dfs_webworker.prompt_optimization.optimization import optimize
from dfs_webworker.prompt_optimization.serialization import serialize
from dfs_webworker.prompt_optimization.utils import (
    data_to_examples,
    init_llm,
    jsdata_to_graph,
)
from dfs_webworker.store import Store
from dfs_webworker.utils import success


@dataclass
class StoredGraph:
    graph: Graph
    llm: LLM


async def prompt_optimization_train(task_spec: dict):
    data = JsData.from_dict(task_spec)
    graph = jsdata_to_graph(data)

    student = init_llm(data.settings.student)
    teacher = init_llm(data.settings.teacher)
    examples = data_to_examples(
        data.dataset,
        inputs=data.settings.inputs,
        outputs=data.settings.outputs,
    )
    print(f"Examples: {examples}")
    print(f"Graph: {graph.llm_repr()}")

    await optimize(
        student=student,
        teacher=teacher,
        graph=graph,
        dataset=data_to_examples(
            data.dataset,
            inputs=data.settings.inputs,
            outputs=data.settings.outputs,
        ),
        task_description=data.settings.task_description,
        evaluation_mode=data.settings.evaluation_mode,
        criteria_list=data.settings.criteria_list,
    )

    model_id = Store.save(StoredGraph(graph=graph, llm=student))

    fe_graph_def = task_spec["data"]
    serialized_model = serialize(
        graph=graph,
        provider=student.provider_name,
        model=data.settings.student.model_id,
        fe_graph_def=fe_graph_def,
    )

    return success(model_id=model_id, model=serialized_model)


async def prompt_optimization_predict(model_id: str, data: dict[str, list]):
    model = Store.get(model_id)

    if not isinstance(model, StoredGraph):
        raise ValueError(f"Model {model_id} is not a valid StoredGraph model")

    graph = model.graph
    llm = model.llm

    keys = list(data.keys())
    values_list = [dict(zip(keys, v)) for v in zip(*data.values())]

    async def predict_row(inputs):
        try:
            return await graph.run(inputs=inputs, llm=llm)
        except InvalidLLMResponseError as error:
            return error

    tasks = [asyncio.create_task(predict_row(d)) for d in values_list]
    try:
        results = await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    failures = [r for r in results if isinstance(r, InvalidLLMResponseError)]
    if failures and len(failures) == len(results):
        raise failures[0]
    if failures:
        return success(
            predictions=[
                None if isinstance(r, InvalidLLMResponseError) else r for r in results
            ],
            prediction_errors=[
                str(r) if isinstance(r, InvalidLLMResponseError) else None
                for r in results
            ],
        )

    return success(predictions=results)
