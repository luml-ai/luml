from abc import ABC, abstractmethod
from promptopt.dataclasses import Socket, StateDescriptor, NodeOutput, LLMExample
from uuid import uuid4


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
