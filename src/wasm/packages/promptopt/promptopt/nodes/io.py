from promptopt.dataclasses import (
    Field,
    Socket,
    StateDescriptor,
    NodeOutput,
    JsonModel,
    OutputSpec,
)
from promptopt.nodes._base import BaseNode
from promptopt.variadic import VariadicList
from uuid import uuid4


class IONode(BaseNode):
    def __init__(self, passthrough: list[Field]):
        self._fields = passthrough
        self._schema = JsonModel(self._fields)

    def to_dict(self):
        return {
            "passthrough": [f.to_dict() for f in self._fields],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IONode":
        if "passthrough" not in data:
            raise ValueError("passthrough field is required")
        return cls([Field.from_dict(f) for f in data["passthrough"]])


class InputNode(IONode):
    def __init__(self, passthrough: list[Field]):
        super().__init__(passthrough)

        self._output_connections = self._output_connections = {
            field.name: OutputSpec([], []) for field in self._fields
        }

    @property
    def listens_to(self) -> list[Socket]:
        return []

    @property
    def reads(self) -> list[StateDescriptor]:
        return []

    @property
    def is_lazy(self) -> bool:
        return False

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

    async def generate(self, inputs, llm, trace) -> NodeOutput:
        validated_inputs = self._schema.validate(inputs)

        all_writes = {}
        all_triggers = []

        for field_name, value in validated_inputs.items():
            output_spec = self._output_connections[field_name]

            if any(state.is_variadic for state in output_spec.states_to_write):
                value = (
                    VariadicList([value])
                    if not isinstance(value, list)
                    else VariadicList(value)
                )

            for state in output_spec.states_to_write:
                all_writes[state] = value

            all_triggers.extend(output_spec.sockets_to_trigger)

        return NodeOutput(writes=all_writes, triggers=all_triggers)

    def get_socket_by_field_name(
        self, field_name: str
    ) -> tuple[Socket, StateDescriptor]:
        raise RuntimeError("InputNode is not supposed to have input sockets")

    @property
    def input_names(self) -> list[str]:
        return []

    @property
    def output_names(self) -> list[str]:
        return [field.name for field in self._fields]


class OutputNode(IONode):
    def __init__(self, passthrough: list[Field]):
        super().__init__(passthrough)
        self._input_sockets = [
            Socket(id=f"{field.name}-{uuid4()}") for field in self._fields
        ]
        self._reads = [
            StateDescriptor(socket.id, field.type, field.is_variadic)
            for field, socket in zip(self._fields, self._input_sockets)
        ]

        self._input_field_to_socket_map = {
            field.name: socket
            for field, socket in zip(passthrough, self._input_sockets)
        }

        self._input_field_to_state_descriptor_map = {
            field.name: state_descriptor
            for field, state_descriptor in zip(self._fields, self._reads)
        }

    @property
    def listens_to(self) -> list[Socket]:
        return self._input_sockets

    @property
    def reads(self) -> list[StateDescriptor]:
        return self._reads

    @property
    def is_lazy(self) -> bool:
        return any(field.is_variadic for field in self._fields)

    def add_output_connection(
        self,
        field_name: str,
        sockets_to_trigger: list[Socket],
        states_to_write: list[StateDescriptor],
    ):
        raise RuntimeError("OutputNode is not supposed to have output connections")

    async def generate(self, inputs, llm, trace) -> NodeOutput:
        return NodeOutput(writes={}, triggers=[])

    def get_socket_by_field_name(
        self, field_name: str
    ) -> tuple[Socket, StateDescriptor]:
        return (
            self._input_field_to_socket_map[field_name],
            self._input_field_to_state_descriptor_map[field_name],
        )

    @property
    def input_names(self) -> list[str]:
        return [field.name for field in self._fields]

    @property
    def output_names(self) -> list[str]:
        return []
