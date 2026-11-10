import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from promptopt.dataclasses import Field
from promptopt.graph import Graph, InputNode, OutputNode, Processor
from promptopt.llm import InvalidLLMResponseError

from dfs_webworker import invoke
from dfs_webworker.prompt_optimization import StoredGraph
from dfs_webworker.store import Store
from dfs_webworker.types import FakeJsProxy


@pytest.fixture
def predict():
    model = StoredGraph(graph=SimpleNamespace(run=AsyncMock()), llm=object())
    model_id = Store.save(model)

    async def call(rows):
        return await invoke(
            "/prompt_optimization/predict",
            FakeJsProxy({"model_id": model_id, "data": {"text": rows}}),
        )

    yield model.graph.run, call
    Store.delete(model_id)


def test_partial_failure_keeps_predictions_in_input_order(predict):
    run, call = predict

    async def row(inputs, llm):
        if inputs["text"] in {"bad", "also bad"}:
            raise InvalidLLMResponseError("Invalid structured response")
        if inputs["text"] == "first":
            await asyncio.sleep(0.01)
        return {"result": inputs["text"]}

    run.side_effect = row
    result = asyncio.run(call(["first", "bad", "last", "also bad"]))

    assert result == {
        "status": "success",
        "predictions": [{"result": "first"}, None, {"result": "last"}, None],
        "prediction_errors": [
            None,
            "Invalid structured response",
            None,
            "Invalid structured response",
        ],
    }


@pytest.mark.parametrize("rows", [["bad"], ["bad", "also bad"]])
def test_all_rows_failing_returns_route_error(predict, rows):
    run, call = predict
    run.side_effect = InvalidLLMResponseError("Invalid structured response")

    result = asyncio.run(call(rows))

    assert result["status"] == "error"
    assert result["error_type"] == "InvalidLLMResponseError"
    assert result["error_message"] == "Invalid structured response"
    assert "predictions" not in result


@pytest.mark.parametrize(
    "error",
    [
        httpx.HTTPStatusError(
            "Unauthorized",
            request=httpx.Request("POST", "https://example.com"),
            response=httpx.Response(401),
        ),
        httpx.ReadTimeout("Timed out"),
        ValueError("Unexpected graph failure"),
    ],
)
def test_provider_error_aborts_and_cancels_pending_rows(predict, error):
    run, call = predict
    cancelled = []

    async def scenario():
        started = asyncio.Event()

        async def row(inputs, llm):
            if inputs["text"] == "provider error":
                await started.wait()
                raise error
            if inputs["text"] == "bad":
                raise InvalidLLMResponseError("Invalid structured response")
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(inputs["text"])

        run.side_effect = row
        result = await asyncio.wait_for(call(["slow", "bad", "provider error"]), 1)
        assert cancelled == ["slow"]
        return result

    result = asyncio.run(scenario())

    assert result["status"] == "error"
    assert result["error_type"] == type(error).__name__
    assert result["error_message"] == str(error)
    assert cancelled == ["slow"]
    assert "predictions" not in result


def test_success_keeps_existing_response_shape(predict):
    run, call = predict
    run.side_effect = [{"result": "first"}, {"result": "second"}]

    assert asyncio.run(call(["first", "second"])) == {
        "status": "success",
        "predictions": [{"result": "first"}, {"result": "second"}],
    }


def test_empty_batch_keeps_existing_response_shape(predict):
    run, call = predict

    assert asyncio.run(call([])) == {"status": "success", "predictions": []}
    run.assert_not_called()


def test_malformed_response_exhausts_retries_without_losing_valid_rows():
    graph = Graph()
    input_node = InputNode([Field("text", "str")])
    processor = Processor([Field("text", "str")], [Field("result", "str")])
    output_node = OutputNode([Field("result", "str")])
    graph.add_node(input_node, "input")
    graph.add_node(processor, "processor")
    graph.add_node(output_node, "output")
    graph.connect(input_node, "text", processor, "text")
    graph.connect(processor, "result", output_node, "result")

    async def generate(messages, out_schema):
        text = json.loads(messages[-1]["content"])["text"]
        return "malformed" if text == "bad" else json.dumps({"result": text})

    llm = SimpleNamespace(generate=AsyncMock(side_effect=generate))
    model_id = Store.save(StoredGraph(graph=graph, llm=llm))
    try:
        result = asyncio.run(
            invoke(
                "/prompt_optimization/predict",
                FakeJsProxy(
                    {
                        "model_id": model_id,
                        "data": {"text": ["first", "second", "bad", "fourth", "last"]},
                    }
                ),
            )
        )
    finally:
        Store.delete(model_id)

    assert result["status"] == "success"
    assert result["predictions"] == [
        {"result": "first"},
        {"result": "second"},
        None,
        {"result": "fourth"},
        {"result": "last"},
    ]
    assert result["prediction_errors"] == [
        None,
        None,
        "Failed to get a valid structured response after 3 attempts.",
        None,
        None,
    ]
    assert llm.generate.await_count == 7
