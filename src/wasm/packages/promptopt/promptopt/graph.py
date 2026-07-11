from typing import Any
import asyncio
from dataclasses import dataclass
from promptopt.nodes._base import BaseNode
from promptopt.dataclasses import Socket, StateDescriptor, NodeOutput
from promptopt.nodes.io import InputNode, OutputNode
from promptopt.nodes.processor import Processor
from promptopt.nodes.gate import Gate
from promptopt.variadic import VariadicList
from promptopt.templates import NODE_LLM_REPR_TEMPLATE, GRAPH_LLM_REPR_TEMPLATE
from promptopt.trace import Trace
from promptopt.llm import LLM
from uuid import uuid4


@dataclass
class GraphState:
    states: dict[StateDescriptor, Any]
    socket_counts: dict[Socket, int]
    active_queue: list[BaseNode]
    lazy_queue: list[BaseNode]

    def update_state(self, state_descriptor: StateDescriptor, value: Any):
        if isinstance(value, VariadicList) and isinstance(
            self.states.get(state_descriptor), VariadicList
        ):
            self.states[state_descriptor].extend(value)
        else:
            self.states[state_descriptor] = value

    def increment_socket_value(self, socket: Socket):
        if socket in self.socket_counts:
            self.socket_counts[socket] += 1
        else:
            self.socket_counts[socket] = 1

    def get_socket_count(self, socket: Socket):
        return self.socket_counts.get(socket, 0)

    def reset_socket_count(self, socket: Socket):
        self.socket_counts[socket] = 0

    def reset_socket_counts(self, sockets: list[Socket]):
        for socket in sockets:
            self.reset_socket_count(socket)

    def apply_node_output(self, node_output: NodeOutput):
        for state_descriptor, value in node_output.writes.items():
            self.update_state(state_descriptor, value)
        for socket in node_output.triggers:
            self.increment_socket_value(socket)

    def reset_queue(self):
        self.active_queue = []
        self.lazy_queue = []


@dataclass
class Edge:
    lhs_node: BaseNode
    lhs_field_name: str
    rhs_node: BaseNode
    rhs_field_name: str

    def to_dict(self):
        return {
            "lhs_node_id": self.lhs_node._injected_node_name,
            "lhs_field_name": self.lhs_field_name,
            "rhs_node_id": self.rhs_node._injected_node_name,
            "rhs_field_name": self.rhs_field_name,
        }


class Graph:
    def __init__(self):
        self.nodes: dict[str, BaseNode] = {}
        self.input_node = None
        self.output_node = None
        self._edges: list[Edge] = []

    def add_node(self, node: BaseNode, node_name: str | None = None):
        if not node_name:
            node_name = node.__class__.__name__.lower() + "_" + str(len(self.nodes))

        if isinstance(node, InputNode):
            if self.input_node:
                raise ValueError("Input node already defined")
            self.input_node = node
        if isinstance(node, OutputNode):
            if self.output_node:
                raise ValueError("Output node already defined")
            self.output_node = node
        if node in self.nodes.values():
            raise ValueError("Node already in graph")
        if node_name in self.nodes:
            raise ValueError("Node name already in graph")
        while node_name in self.nodes:
            node_name += str(uuid4())[:4]

        self.nodes[node_name] = node
        node._injected_node_name = node_name

    def connect(
        self, lhs_node: BaseNode, lhs_field: str, rhs_node: BaseNode, rhs_field: str
    ):
        if lhs_node not in self.nodes.values() and lhs_node is not self.input_node:
            raise ValueError("LHS node not in graph")
        if rhs_node not in self.nodes.values():
            raise ValueError("RHS node not in graph")

        if len(rhs_node.listens_to) < 1:
            raise ValueError("RHS node has no input sockets")

        rhs_socket, rhs_state_descriptor = rhs_node.get_socket_by_field_name(rhs_field)

        lhs_node.add_output_connection(
            output_field_name=lhs_field,
            sockets_to_trigger=[rhs_socket],
            states_to_write=[rhs_state_descriptor],
        )

        self._edges.append(Edge(lhs_node, lhs_field, rhs_node, rhs_field))

    def _schedule_node(self, node: BaseNode, state: GraphState):
        if node in state.active_queue or node in state.lazy_queue:
            return

        if node.is_lazy:
            state.lazy_queue.append(node)
        else:
            state.active_queue.append(node)

    def _fill_queue(self, state: GraphState):
        for node in self.nodes.values():
            if node is self.input_node:
                continue
            if all(state.get_socket_count(socket) > 0 for socket in node.listens_to):
                self._schedule_node(node, state)

    def _get_node_inputs(self, node: BaseNode, state: GraphState):
        return {
            field_name: state.states[state_descriptor]
            for field_name, state_descriptor in zip(node.input_names, node.reads)
        }

    async def run(
        self, inputs: dict, llm: LLM, trace: Trace | None = None
    ) -> dict[str, Any]:
        if not self.input_node:
            raise ValueError("No input node defined")
        if not self.output_node:
            raise ValueError("No output node defined")
        state = GraphState(states={}, socket_counts={}, active_queue=[], lazy_queue=[])

        input_node_result = await self.input_node.generate(inputs, llm, trace)

        state.apply_node_output(input_node_result)

        step = 0
        while True:
            self._fill_queue(state)

            if len(state.active_queue) > 0:
                next_nodes = state.active_queue
            elif len(state.lazy_queue) > 0:
                next_nodes = state.lazy_queue
            else:
                raise RuntimeError("No nodes to run")
            step += 1

            tasks: list[tuple[BaseNode, Any]] = []

            for node in next_nodes:
                node_inputs = self._get_node_inputs(node, state)

                tasks.append((node, node.generate(node_inputs, llm, trace)))

            results: list[NodeOutput] = await asyncio.gather(
                *(task for _, task in tasks)
            )

            for (node, _), node_output in zip(tasks, results):
                state.reset_socket_counts(node.listens_to)
                state.apply_node_output(node_output)

            if self.output_node in next_nodes:
                return self._get_node_inputs(self.output_node, state)

            state.reset_queue()

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "name": node_name,
                    "type": node.__class__.__name__,
                    "kwargs": node.to_dict(),
                }
                for node_name, node in self.nodes.items()
            ],
            "edges": [edge.to_dict() for edge in self._edges],
        }

    def llm_repr(self):
        nodes_repr = []
        edges_repr = []
        if not self.input_node:
            raise ValueError("No input node defined")
        for node_name, node in self.nodes.items():
            nodes_repr.append(
                NODE_LLM_REPR_TEMPLATE.format(
                    id=node_name,
                    type=node.__class__.__name__,
                    inputs=str(node.input_names),
                    outputs=str(node.output_names),
                    hint=f"Hint: {node.hint}" if node.hint else "",
                )
            )

        for edge in self._edges:
            edges_repr.append(
                f"{edge.lhs_node._injected_node_name}.{edge.lhs_field_name} -> {edge.rhs_node._injected_node_name}.{edge.rhs_field_name}"
            )

        return GRAPH_LLM_REPR_TEMPLATE.format(
            nodes="\n".join(nodes_repr), edges="\n".join(edges_repr)
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Graph":
        graph = cls()

        node_types: dict[str, type[BaseNode]] = {
            "InputNode": InputNode,
            "OutputNode": OutputNode,
            "Processor": Processor,
            "Gate": Gate,
        }

        for node_data in data["nodes"]:
            node_class = node_types.get(node_data["type"], None)
            if node_class is None:
                raise ValueError(f"Unknown node type: {node_data['type']}")
            node = node_class.from_dict(node_data["kwargs"])
            graph.add_node(node, node_data["name"])

        for edge_data in data["edges"]:
            lhs_node = graph.nodes[edge_data["lhs_node_id"]]
            rhs_node = graph.nodes[edge_data["rhs_node_id"]]
            graph.connect(
                lhs_node,
                edge_data["lhs_field_name"],
                rhs_node,
                edge_data["rhs_field_name"],
            )

        return graph
