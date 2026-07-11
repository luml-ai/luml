from dataclasses import dataclass
from typing import Type, Any


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
