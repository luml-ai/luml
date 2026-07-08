# This file is auto-generated. Do not edit.

import asyncio
import httpx
import json

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Type
from uuid import uuid4



@dataclass
class Socket:
    id: str

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class StateDescriptor:
    name: str
    type: Type | str
    is_variadic: bool = False

    def __hash__(self) -> int:
        return hash(id(self))


@dataclass
class Field:
    name: str
    type: str
    is_variadic: bool = False
    allowed_values: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "is_variadic": self.is_variadic,
            "allowed_values": self.allowed_values,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Field":
        return cls(
            name=data["name"],
            type=data["type"],
            is_variadic=data["is_variadic"],
            allowed_values=data.get("allowed_values"),
        )


@dataclass
class JsonModel:
    fields: list[Field]

    def model_json_schema(self) -> dict[str, Any]:
        properties = {}
        required = []

        for field in self.fields:
            type_mapping = {
                "str": {"type": "string"},
                "int": {"type": "integer"},
                "float": {"type": "number"},
                "bool": {"type": "boolean"},
                "list": {"type": "array"},
                "dict": {"type": "object"},
                "string": {"type": "string"},
                "integer": {"type": "integer"},
            }
            field_schema: dict[str, Any]
            if field.type in type_mapping:
                field_schema = type_mapping[field.type].copy()
            else:
                field_schema = {"type": "object"}

            if field.allowed_values:
                field_schema["enum"] = field.allowed_values

            if field.is_variadic:
                field_schema = {"type": "array", "items": field_schema}

            properties[field.name] = field_schema
            required.append(field.name)

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

        return schema

    @staticmethod
    def _validate_scalar_type(value: Any, field_type: str) -> bool:
        if field_type in {"str", "string"}:
            return isinstance(value, str)
        if field_type in {"int", "integer"}:
            return isinstance(value, int) and not isinstance(value, bool)
        if field_type == "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if field_type == "bool":
            return isinstance(value, bool)
        if field_type == "list":
            return isinstance(value, list)
        if field_type == "dict":
            return isinstance(value, dict)
        return True

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        fields_by_name = {field.name: field for field in self.fields}

        missing_fields = [field.name for field in self.fields if field.name not in data]
        if missing_fields:
            missing_joined = ", ".join(missing_fields)
            raise ValueError(f"Missing required fields: {missing_joined}")

        unexpected_fields = [key for key in data if key not in fields_by_name]
        if unexpected_fields:
            unexpected_joined = ", ".join(unexpected_fields)
            raise ValueError(f"Unexpected fields: {unexpected_joined}")

        for field_name, value in data.items():
            field = fields_by_name[field_name]

            if field.is_variadic:
                if not isinstance(value, list):
                    raise ValueError(f"Field {field.name} must be a list.")
                values_to_validate = value
            else:
                values_to_validate = [value]

            for item in values_to_validate:
                if not self._validate_scalar_type(item, field.type):
                    raise ValueError(
                        f"Field {field.name} must be of type {field.type}."
                    )

                if field.allowed_values is not None and item not in field.allowed_values:
                    raise ValueError(
                        f"Field {field.name} must be one of {field.allowed_values}."
                    )

        return data


@dataclass
class NodeOutput:
    writes: dict[StateDescriptor, Any]
    triggers: list[Socket]


@dataclass
class OutputSpec:
    states_to_write: list[StateDescriptor]
    sockets_to_trigger: list[Socket]


@dataclass
class LLMExample:
    input: str
    output: str


@dataclass
class Example:
    input: dict
    output: dict



class BaseNode(ABC):
    _injected_node_name: str = ""
    _instruction: str | None = None
    _examples: list[LLMExample] | None = None
    _frozen_id: int | None = None
    hint: str | None = None

    @property
    @abstractmethod
    def input_names(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def output_names(self) -> list[str]:
        pass

    @property
    @abstractmethod
    def listens_to(self) -> list[Socket]:
        pass

    @property
    @abstractmethod
    def reads(self) -> list[StateDescriptor]:
        pass

    @property
    @abstractmethod
    def is_lazy(self) -> bool:
        pass

    @abstractmethod
    def add_output_connection(
        self,
        output_field_name: str,
        sockets_to_trigger: list[Socket],
        states_to_write: list[StateDescriptor],
    ):
        pass

    @abstractmethod
    def get_socket_by_field_name(
        self, field_name: str
    ) -> tuple[Socket, StateDescriptor]:
        pass

    @abstractmethod
    def generate(self, inputs, llm, trace) -> NodeOutput:
        pass

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "BaseNode":
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._injected_node_name}>"

    def set_examples(self, examples: list[LLMExample]) -> None:
        self._examples = examples

    def set_instruction(self, instruction: str) -> None:
        self._instruction = instruction

class VariadicList(list):
    def __repr__(self):
        return f"VariadicList<{super().__repr__()}>"



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

NODE_SYSTEM_PROMPT_TEMPLATE = """You are provided with an input schema, an output schema and an instruction. Answer with a JSON matching the output schema.

Input schema:
{input_schema}

Output schema:
{output_schema}

Instruction:
{instruction}
"""


GRAPH_LLM_REPR_TEMPLATE = """=====
Nodes:

{nodes}
======
Edges:

{edges}
======
"""

NODE_LLM_REPR_TEMPLATE = """ID: {id}
Type: {type}
Inputs: {inputs}
Outputs: {outputs}
{hint}
"""



class LLM(ABC):
    provider_name: str

    @abstractmethod
    async def generate(self, messages: list, out_schema) -> str:
        pass

    @abstractmethod
    async def batch_generate(
        self,
        messages: list,
        temperature: float = 0.0,
        n_responses: int = 1,
    ) -> list[str]:
        pass

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        raise NotImplementedError()


class OpenAIProvider(LLM):
    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com",
        model="gpt-4o-mini",
        max_parallel_requests: int = 16,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._semaphore = asyncio.Semaphore(max_parallel_requests)

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": response_format,
            "stream": False,
            **kwargs,
        }

        async with self._semaphore:
            async with httpx.AsyncClient() as client:
                retries = 3
                for attempt in range(retries):
                    try:
                        response = await client.post(
                            url, json=payload, headers=headers, timeout=60.0
                        )
                        response.raise_for_status()
                        return response.json()
                    except httpx.HTTPStatusError as e:
                        print(
                            "Attempt",
                            attempt + 1,
                            "failed with status code:",
                            e.response.status_code,
                        )
                        if attempt >= retries - 1:
                            print("Response Text:", e.response.text)
                            raise
                        await asyncio.sleep(delay=2**attempt)
        raise RuntimeError("Failed to get a valid response after multiple attempts.")

    async def generate(self, messages: list, out_schema) -> str:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "OutputSchema",
                "schema": out_schema.model_json_schema(),
                "strict": True,
            },
        }

        out = await self.chat(
            model=self.model, messages=messages, response_format=response_format
        )

        return out["choices"][0]["message"]["content"]  # type: ignore

    async def batch_generate(
        self, messages: list, temperature: float = 0, n_responses: int = 1
    ):
        out = await self.chat(
            model=self.model,
            messages=messages,
            temperature=temperature,
            n=n_responses,
        )

        return [
            out["choices"][i]["message"]["content"]  # type: ignore
            for i in range(len(out["choices"]))
        ]


class OllamaProvider(LLM):
    provider_name = "ollama"

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "llama3.2:1b"
    ):
        self.base_url = base_url
        self.model = model

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        url = f"{self.base_url}/api/chat"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": response_format,
            "options": {
                "temperature": temperature,
                **kwargs,
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def generate(self, messages: list, out_schema) -> str:
        out = await self.chat(
            model=self.model,
            messages=messages,
            response_format=out_schema.model_json_schema(),
        )

        return out["message"]["content"]  # type: ignore

    async def batch_generate(
        self,
        messages: list,
        temperature: float = 0.0,
        n_responses: int = 1,
    ) -> list[str]:
        tasks = []
        for _ in range(n_responses):
            task = self.chat(
                model=self.model, messages=messages, temperature=temperature
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        return [resp["message"]["content"] for resp in responses]



class Trace:
    def __init__(self):
        self._examples: dict[int, list[LLMExample]] = {}

    def add_example(self, key: object, input: str, output: str):
        if id(key) not in self._examples:
            self._examples[id(key)] = []
        self._examples[id(key)].append(LLMExample(input, output))

    def __repr__(self) -> str:
        str_ = "Trace:"
        for key, examples in self._examples.items():
            str_ += f"\n\t{key}:"
            for example in examples:
                str_ += f"\n\t\t{example.input} -> {example.output}"
        return str_



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



class Gate(BaseNode):
    _default_instruction = "Classify the input into one of the output classes."

    def __init__(
        self,
        classification_field: Field,
        output_classes: list[str],
    ) -> None:
        self.classification_field = classification_field
        self.output_classes = output_classes

        self._input_sockets = [Socket(id=f"{classification_field.name}-{uuid4()}")]
        self._output_connections = {
            label: OutputSpec([], []) for label in output_classes
        }

        self._reads = [
            StateDescriptor(
                self._input_sockets[0].id,
                classification_field.type,
                classification_field.is_variadic,
            )
        ]

        self.input_schema = JsonModel([classification_field])
        self.output_schema = JsonModel(
            [Field("classification", "str", allowed_values=output_classes)]
        )

    @property
    def input_names(self) -> list[str]:
        return [self.classification_field.name]

    @property
    def output_names(self) -> list[str]:
        return self.output_classes

    @property
    def listens_to(self) -> list[Socket]:
        return self._input_sockets

    @property
    def reads(self) -> list[StateDescriptor]:
        return self._reads

    @property
    def is_lazy(self) -> bool:
        return self.classification_field.is_variadic

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

    def get_socket_by_field_name(
        self, field_name: str
    ) -> tuple[Socket, StateDescriptor]:
        if field_name != self.classification_field.name:
            raise ValueError(f"No field named {field_name}")
        return self._input_sockets[0], self._reads[0]

    def _generate_instruction(self) -> str:
        return NODE_SYSTEM_PROMPT_TEMPLATE.format(
            input_schema=self.input_schema.model_json_schema(),
            output_schema=self.output_schema.model_json_schema(),
            instruction=self._instruction or self._default_instruction,
        )

    async def generate(self, inputs, llm, trace) -> NodeOutput:
        inputs_json = json.dumps(inputs)

        instruction = self._generate_instruction()

        messages = [
            {"role": "system", "content": instruction},
        ]

        for example in self._examples or []:
            messages.append(
                {
                    "role": "user",
                    "content": example.input,
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": example.output,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": inputs_json,
            }
        )

        classification_result_str = await llm.generate(
            messages,
            out_schema=self.output_schema,
        )

        if trace:
            trace.add_example(self, inputs_json, classification_result_str)

        classification_result = json.loads(classification_result_str)

        classification = classification_result["classification"]

        if classification not in self.output_classes:
            raise ValueError(f"Invalid classification result: {classification}")

        return NodeOutput(
            writes={
                s: inputs[self.classification_field.name]
                for s in self._output_connections[classification].states_to_write
            },
            triggers=self._output_connections[classification].sockets_to_trigger,
        )

    def to_dict(self) -> dict:
        return {
            "classification_field": self.classification_field.to_dict(),
            "output_classes": self.output_classes,
            "examples": [
                {"input": e.input, "output": e.output} for e in self._examples or []
            ],
            "instruction": self._instruction,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Gate":
        if "classification_field" not in data:
            raise ValueError("classification_field is required")
        if "output_classes" not in data:
            raise ValueError("output_classes is required")

        classification_field = Field.from_dict(data["classification_field"])
        output_classes = data["output_classes"]
        node = cls(classification_field, output_classes)
        examples = [
            LLMExample(example["input"], example["output"])
            for example in data.get("examples", [])
        ]
        instruction = data.get("instruction", None)
        node._examples = examples
        node._instruction = instruction
        return node



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

from fnnx.variants.pyfunc import PyFunc


class GraphPyFunc(PyFunc):
    def warmup(self):
        self.graph_spec = self.fnnx_context.get_value("graph")
        if not isinstance(self.graph_spec, dict):
            raise ValueError("Graph spec must be a dictionary")
        self.provider = self.fnnx_context.get_value("provider")
        self.graph = Graph.from_dict(self.graph_spec)
#
    def _get_client(self, dynamic_attributes: dict):
        if self.provider == "openai":
            api_key = dynamic_attributes.get("api_key")
            if not isinstance(api_key, str):
                raise ValueError("API key must be a string")
            model_id = self.fnnx_context.get_value("model_id")
            if not isinstance(model_id, str):
                raise ValueError(
                    f"Model ID must be a string, got {type(model_id)} :: {model_id}"
                )
            return OpenAIProvider(model=model_id, api_key=api_key)
        elif self.provider == "ollama":
            base_url = dynamic_attributes.get("base_url")
            if not isinstance(base_url, str):
                raise ValueError("Base url must be a string")
            model_id = self.fnnx_context.get_value("model_id")
            if not isinstance(model_id, str):
                raise ValueError(
                    f"Model ID must be a string, got {type(model_id)} :: {model_id}"
                )
            return OllamaProvider(model=model_id, base_url=base_url)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
#
    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        raise NotImplementedError("Only async compute is supported")
#
    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        client = self._get_client(dynamic_attributes)
        return {"out": await self.graph.run(inputs["in"], client)}
