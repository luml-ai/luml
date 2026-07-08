from promptopt.dataclasses import (
    Field,
    Socket,
    StateDescriptor,
    NodeOutput,
    JsonModel,
    OutputSpec,
)
from promptopt.nodes._base import BaseNode
from promptopt.templates import NODE_SYSTEM_PROMPT_TEMPLATE
from promptopt.dataclasses import LLMExample
from uuid import uuid4
import json


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
