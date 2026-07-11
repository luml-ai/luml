from promptopt.nodes._base import BaseNode
from promptopt.dataclasses import (
    Field,
    Socket,
    StateDescriptor,
    JsonModel,
    OutputSpec,
    NodeOutput,
)
from promptopt.templates import NODE_SYSTEM_PROMPT_TEMPLATE
from promptopt.llm import LLM
from promptopt.variadic import VariadicList
from promptopt.dataclasses import LLMExample
from promptopt.trace import Trace
from uuid import uuid4
import json


class Processor(BaseNode):
    _default_instruction = "Generate an output following the output schema format."

    def __init__(
        self,
        inputs: list[Field],
        outputs: list[Field],
    ):
        self._inputs = inputs
        self._outputs = outputs

        self._input_schema = JsonModel(self._inputs)
        self._output_schema = JsonModel(self._outputs)

        self._input_sockets = [
            Socket(id=f"{field.name}-{uuid4()}") for field in self._inputs
        ]

        self._output_connections: dict[str, OutputSpec] = {
            field.name: OutputSpec(states_to_write=[], sockets_to_trigger=[])
            for field in self._outputs
        }

        self._input_field_to_socket_map = {
            field.name: socket
            for field, socket in zip(self._inputs, self._input_sockets)
        }

        self._reads = [
            StateDescriptor(socket.id, field.type, field.is_variadic)
            for field, socket in zip(self._inputs, self._input_sockets)
        ]

        self._input_field_to_state_descriptor_map = {
            field.name: state_descriptor
            for field, state_descriptor in zip(self._inputs, self._reads)
        }

        self._is_lazy = any(field.is_variadic for field in self._inputs)

    @property
    def listens_to(self) -> list[Socket]:
        return self._input_sockets

    @property
    def reads(self):
        return self._reads

    @property
    def is_lazy(self) -> bool:
        return self._is_lazy

    @property
    def input_names(self) -> list[str]:
        return [field.name for field in self._inputs]

    @property
    def output_names(self) -> list[str]:
        return [field.name for field in self._outputs]

    def add_output_connection(
        self,
        output_field_name: str,
        sockets_to_trigger: list[Socket],
        states_to_write: list[StateDescriptor],
    ):
        if output_field_name not in self._output_connections:
            raise ValueError(f"No output field named {output_field_name}")
        self._output_connections[output_field_name].sockets_to_trigger.extend(
            sockets_to_trigger
        )
        self._output_connections[output_field_name].states_to_write.extend(
            states_to_write
        )

    def _generate_instruction(self):
        return NODE_SYSTEM_PROMPT_TEMPLATE.format(
            input_schema=self._input_schema.model_json_schema(),
            output_schema=self._output_schema.model_json_schema(),
            instruction=self._instruction or self._default_instruction,
        )

    async def generate(
        self, inputs: dict, llm: LLM, trace: Trace | None = None
    ) -> NodeOutput:
        system_message = self._generate_instruction()
        inputs = self._input_schema.validate(inputs)
        inputs_json = json.dumps(inputs)
        messages = [
            {"role": "system", "content": system_message},
        ]

        for example in self._examples or []:
            messages.append({"role": "user", "content": example.input})
            messages.append({"role": "assistant", "content": example.output})

        messages.append({"role": "user", "content": inputs_json})

        output_str = await llm.generate(messages, out_schema=self._output_schema)

        if trace is not None:
            trace.add_example(self, inputs_json, output_str)

        output = json.loads(output_str)

        sockets_to_trigger = []
        fields_to_write = {}

        for out_field, (out_connection, out_spec) in zip(
            self._outputs, self._output_connections.items()
        ):
            output_value = output.get(out_field.name)

            if (
                len(out_spec.states_to_write) > 0
                and out_spec.states_to_write[0].is_variadic
            ):
                output_value = VariadicList(
                    output_value if isinstance(output_value, list) else [output_value]
                )

            sockets_to_trigger.extend(
                self._output_connections[out_connection].sockets_to_trigger
            )

            for state_to_write in self._output_connections[
                out_connection
            ].states_to_write:
                fields_to_write[state_to_write] = output_value
        return NodeOutput(writes=fields_to_write, triggers=sockets_to_trigger)

    def get_socket_by_field_name(
        self, field_name: str
    ) -> tuple[Socket, StateDescriptor]:
        return (
            self._input_field_to_socket_map[field_name],
            self._input_field_to_state_descriptor_map[field_name],
        )

    def to_dict(self) -> dict:
        return {
            "inputs": [field.to_dict() for field in self._inputs],
            "outputs": [field.to_dict() for field in self._outputs],
            "examples": [
                {"input": example.input, "output": example.output}
                for example in self._examples or []
            ],
            "instruction": self._instruction,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Processor":
        inputs = [Field.from_dict(field) for field in data["inputs"]]
        outputs = [Field.from_dict(field) for field in data["outputs"]]
        examples = [
            LLMExample(example["input"], example["output"])
            for example in data.get("examples", [])
        ]
        instruction = data.get("instruction", None)
        node = cls(inputs, outputs)
        node._examples = examples
        node._instruction = instruction
        return node
