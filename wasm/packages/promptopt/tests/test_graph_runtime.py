import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest

from promptopt.dataclasses import Field, NodeOutput, OutputSpec, Socket, StateDescriptor
from promptopt.graph import Graph
from promptopt.llm import InvalidLLMResponseError
from promptopt.nodes._base import BaseNode
from promptopt.nodes.io import InputNode, OutputNode
from promptopt.variadic import VariadicList


class RelayNode(BaseNode):
    def __init__(
        self,
        input_field: str,
        output_field: str,
        transform: Callable[[Any], Any],
        is_lazy: bool = False,
        input_is_variadic: bool = False,
        call_log: list[str] | None = None,
        label: str | None = None,
    ) -> None:
        self._input_field = input_field
        self._output_field = output_field
        self._transform = transform
        self._is_lazy = is_lazy
        self._call_log = call_log
        self._label = label or output_field

        self._input_socket = Socket(f"{input_field}-{uuid4()}")
        self._read = StateDescriptor(
            self._input_socket.id,
            "str",
            is_variadic=input_is_variadic,
        )
        self._output_connections = {
            output_field: OutputSpec(states_to_write=[], sockets_to_trigger=[])
        }

    @property
    def input_names(self) -> list[str]:
        return [self._input_field]

    @property
    def output_names(self) -> list[str]:
        return [self._output_field]

    @property
    def listens_to(self) -> list[Socket]:
        return [self._input_socket]

    @property
    def reads(self) -> list[StateDescriptor]:
        return [self._read]

    @property
    def is_lazy(self) -> bool:
        return self._is_lazy

    def add_output_connection(
        self,
        output_field_name: str,
        sockets_to_trigger: list[Socket],
        states_to_write: list[StateDescriptor],
    ) -> None:
        if output_field_name not in self._output_connections:
            raise ValueError(f"No output field named {output_field_name}")

        self._output_connections[output_field_name].sockets_to_trigger.extend(
            sockets_to_trigger
        )
        self._output_connections[output_field_name].states_to_write.extend(
            states_to_write
        )

    def get_socket_by_field_name(
        self, field_name: str
    ) -> tuple[Socket, StateDescriptor]:
        if field_name != self._input_field:
            raise ValueError(f"No field named {field_name}")
        return self._input_socket, self._read

    async def generate(
        self, inputs: dict[str, Any], llm: Any, trace: Any
    ) -> NodeOutput:
        if self._call_log is not None:
            self._call_log.append(self._label)

        output_value = self._transform(inputs[self._input_field])
        out_spec = self._output_connections[self._output_field]

        if any(state.is_variadic for state in out_spec.states_to_write):
            if isinstance(output_value, list):
                output_value = VariadicList(output_value)
            else:
                output_value = VariadicList([output_value])

        writes = {state: output_value for state in out_spec.states_to_write}
        return NodeOutput(writes=writes, triggers=out_spec.sockets_to_trigger)

    def to_dict(self) -> dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelayNode":
        raise NotImplementedError()


class ScriptedNode(RelayNode):
    def __init__(self, output_field: str, script: Callable[[], Awaitable[None]]):
        super().__init__("x", output_field, lambda value: value)
        self._script = script

    async def generate(
        self, inputs: dict[str, Any], llm: Any, trace: Any
    ) -> NodeOutput:
        await self._script()
        return await super().generate(inputs, llm, trace)


def _fan_out_graph(
    left: Callable[[], Awaitable[None]], right: Callable[[], Awaitable[None]]
) -> Graph:
    graph = Graph()
    input_node = InputNode([Field("x", "str")])
    output_node = OutputNode([Field("left", "str"), Field("right", "str")])

    graph.add_node(input_node, "input")
    graph.add_node(output_node, "output")
    for name, script in [("left", left), ("right", right)]:
        node = ScriptedNode(name, script)
        graph.add_node(node, name)
        graph.connect(input_node, "x", node, "x")
        graph.connect(node, name, output_node, name)

    return graph


def test_graph_connect_and_run_routes_state() -> None:
    graph = Graph()
    input_node = InputNode([Field("x", "str")])
    relay = RelayNode("x", "y", lambda value: f"{value}_processed")
    output_node = OutputNode([Field("y", "str")])

    graph.add_node(input_node, "input")
    graph.add_node(relay, "relay")
    graph.add_node(output_node, "output")

    graph.connect(input_node, "x", relay, "x")
    graph.connect(relay, "y", output_node, "y")

    result = asyncio.run(graph.run({"x": "item"}, llm=None))
    assert result == {"y": "item_processed"}


def test_active_batch_runs_before_lazy_batch() -> None:
    call_log: list[str] = []

    graph = Graph()
    input_node = InputNode([Field("x", "str")])

    def _normalize(value: Any) -> str:
        if isinstance(value, list):
            return str(value[0])
        return str(value)

    active = RelayNode(
        "x",
        "out",
        lambda value: f"{_normalize(value)}_active",
        call_log=call_log,
        label="active",
    )
    lazy = RelayNode(
        "x",
        "ignored",
        lambda value: f"{value}_lazy",
        is_lazy=True,
        input_is_variadic=True,
        call_log=call_log,
        label="lazy",
    )
    output_node = OutputNode([Field("out", "str")])

    graph.add_node(input_node, "input")
    graph.add_node(active, "active")
    graph.add_node(lazy, "lazy")
    graph.add_node(output_node, "output")

    graph.connect(input_node, "x", active, "x")
    graph.connect(active, "out", output_node, "out")
    graph.connect(input_node, "x", lazy, "x")

    result = asyncio.run(graph.run({"x": "item"}, llm=None))

    assert result == {"out": "item_active"}
    assert call_log == ["active"]


def test_variadic_writes_append_across_multiple_nodes() -> None:
    graph = Graph()
    input_node = InputNode([Field("x", "str")])
    left = RelayNode("x", "item", lambda value: f"left_{value}")
    right = RelayNode("x", "item", lambda value: f"right_{value}")
    output_node = OutputNode([Field("items", "str", is_variadic=True)])

    graph.add_node(input_node, "input")
    graph.add_node(left, "left")
    graph.add_node(right, "right")
    graph.add_node(output_node, "output")

    graph.connect(input_node, "x", left, "x")
    graph.connect(input_node, "x", right, "x")
    graph.connect(left, "item", output_node, "items")
    graph.connect(right, "item", output_node, "items")

    result = asyncio.run(graph.run({"x": "value"}, llm=None))

    assert isinstance(result["items"], VariadicList)
    assert list(result["items"]) == ["left_value", "right_value"]


def test_malformed_node_does_not_hide_sibling_provider_error() -> None:
    async def scenario() -> None:
        malformed = asyncio.Event()

        async def fail_malformed() -> None:
            malformed.set()
            raise InvalidLLMResponseError("malformed")

        async def fail_provider() -> None:
            await malformed.wait()
            await asyncio.sleep(0)
            raise RuntimeError("provider")

        graph = _fan_out_graph(fail_malformed, fail_provider)
        with pytest.raises(RuntimeError, match="provider"):
            await graph.run({"x": "item"}, llm=None)

    asyncio.run(scenario())


def test_malformed_node_raises_after_sibling_nodes_finish() -> None:
    finished: list[str] = []

    async def scenario() -> None:
        async def fail_malformed() -> None:
            raise InvalidLLMResponseError("malformed")

        async def succeed_later() -> None:
            await asyncio.sleep(0.01)
            finished.append("right")

        graph = _fan_out_graph(fail_malformed, succeed_later)
        with pytest.raises(InvalidLLMResponseError, match="malformed"):
            await graph.run({"x": "item"}, llm=None)
        assert finished == ["right"]

    asyncio.run(scenario())


def test_provider_error_cancels_sibling_nodes() -> None:
    cancelled: list[str] = []

    async def scenario() -> None:
        started = asyncio.Event()

        async def fail_provider() -> None:
            await started.wait()
            raise RuntimeError("provider")

        async def wait_forever() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append("right")
                raise

        graph = _fan_out_graph(fail_provider, wait_forever)
        with pytest.raises(RuntimeError, match="provider"):
            await graph.run({"x": "item"}, llm=None)
        assert cancelled == ["right"]

    asyncio.run(scenario())
