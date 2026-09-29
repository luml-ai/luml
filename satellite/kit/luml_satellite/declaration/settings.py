import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, StrEnum
from types import UnionType
from typing import Any, Literal, Self, Union, cast, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

type SettingScalar = bool | int | str
type DropdownScalar = int | str
type FieldOperator = Literal[
    "includes",
    "notIncludes",
    "equal",
    "notEqual",
    "gt",
    "gte",
    "lt",
    "lte",
]
type ModelField = Literal["tags", "version", "variant"]
type ModelOperator = Literal["includes", "notIncludes", "eq", "neq"]
type ValidatorType = Literal["min", "max", "regex", "equal", "in", "notEqual"]

_FIELD_OPERATORS = frozenset(
    {"includes", "notIncludes", "equal", "notEqual", "gt", "gte", "lt", "lte"}
)
_MODEL_OPERATORS = {
    "tags": frozenset({"includes", "notIncludes"}),
    "version": frozenset({"eq", "neq"}),
    "variant": frozenset({"eq", "neq", "includes", "notIncludes"}),
}
_VALIDATOR_TYPES = frozenset({"min", "max", "regex", "equal", "in", "notEqual"})
_METADATA_KEY = "luml_satellite_setting"


class SettingsDeclarationError(TypeError):
    pass


class SettingsValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"Invalid deployment settings: {field}: {message}")


@dataclass(frozen=True)
class DropdownValue:
    label: str
    value: DropdownScalar


@dataclass(frozen=True)
class SettingsValidator:
    type: ValidatorType
    value: object
    message: str | None = None


@dataclass(frozen=True)
class FieldCondition:
    field: str
    operator: FieldOperator
    value: object = None


@dataclass(frozen=True)
class ModelCondition:
    field: ModelField
    operator: ModelOperator
    value: object


@dataclass(frozen=True, init=False)
class ConditionGroup:
    conditions: tuple[object, ...]

    def __init__(self, *conditions: object) -> None:
        object.__setattr__(self, "conditions", conditions)


def setting_field(
    default: object = PydanticUndefined,
    *,
    exposed: bool = True,
    values: Sequence[DropdownValue | tuple[str, DropdownScalar] | DropdownScalar] | None = None,
    conditions: Sequence[
        FieldCondition | ModelCondition | ConditionGroup | Mapping[str, object]
    ] = (),
    validators: Sequence[SettingsValidator | Mapping[str, object]] = (),
    ge: int | None = None,
    le: int | None = None,
    pattern: str | None = None,
) -> Any:  # noqa: ANN401
    metadata: dict[str, object] = {
        "exposed": exposed,
        "values": _normalize_dropdown_values(values),
        "conditions": [_normalize_condition(condition) for condition in conditions],
        "validators": [_normalize_validator(validator) for validator in validators],
    }
    return Field(
        default=default,
        ge=ge,
        le=le,
        pattern=pattern,
        json_schema_extra=cast(dict[str, Any], {_METADATA_KEY: metadata}),
    )


class DeploymentSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_default=True)

    health_check_timeout: int = Field(
        ge=1,
        json_schema_extra={
            _METADATA_KEY: {
                "exposed": False,
                "values": [],
                "conditions": [],
                "validators": [],
            }
        },
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: object) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        _validate_settings_model(cls)

    @classmethod
    def from_parameters(
        cls,
        parameters: Mapping[str, object] | None,
        *,
        default_health_check_timeout: int = 1800,
    ) -> Self:
        return parse_settings(
            cls,
            parameters,
            default_health_check_timeout=default_health_check_timeout,
        )

    @model_validator(mode="after")
    def _validate_declared_values(self) -> Self:
        for name, field in type(self).model_fields.items():
            value = getattr(self, name)
            if value is None:
                continue
            metadata = _setting_metadata(field)
            options = _metadata_list(metadata, "values")
            if options and value not in {option["value"] for option in options}:
                raise ValueError(f"{name}: value is not one of the declared dropdown values")
            for validator in _metadata_list(metadata, "validators"):
                if not _validator_accepts(value, validator):
                    message = validator.get("message")
                    detail = str(message) if message is not None else f"failed {validator['type']}"
                    raise ValueError(f"{name}: {detail}")
        return self


def parse_settings[SettingsType: DeploymentSettings](
    settings_type: type[SettingsType],
    parameters: Mapping[str, object] | None,
    *,
    default_health_check_timeout: int = 1800,
) -> SettingsType:
    values = dict(parameters or {})
    health_field = settings_type.model_fields.get("health_check_timeout")
    if (
        health_field is not None
        and "health_check_timeout" not in values
        and health_field.is_required()
    ):
        values["health_check_timeout"] = default_health_check_timeout
    try:
        return settings_type.model_validate(values)
    except ValidationError as error:
        field, message = _settings_error(error, settings_type)
        raise SettingsValidationError(field, message) from error


def settings_fields(settings_type: type[DeploymentSettings]) -> list[dict[str, object]]:
    _validate_settings_model(settings_type)
    declarations: list[dict[str, object]] = []
    for name, field in settings_type.model_fields.items():
        metadata = _setting_metadata(field)
        if metadata.get("exposed", True) is False:
            continue
        field_type, options = _field_type_and_values(name, field, metadata)
        declaration: dict[str, object] = {
            "name": name,
            "type": field_type,
            "values": options,
            "required": field.is_required(),
            "validators": _field_validators(field, metadata),
            "conditions": _metadata_list(metadata, "conditions"),
        }
        if not field.is_required():
            declaration["default"] = _wire_value(field.get_default(call_default_factory=True))
        declarations.append(declaration)
    return declarations


def _validate_settings_model(settings_type: type[DeploymentSettings]) -> None:
    field_names = set(settings_type.model_fields)
    for name, field in settings_type.model_fields.items():
        metadata = _setting_metadata(field)
        _field_type_and_values(name, field, metadata)
        for condition in _metadata_list(metadata, "conditions"):
            for referenced in _condition_field_references(condition):
                if referenced not in field_names:
                    raise SettingsDeclarationError(
                        f"field '{name}' condition references undeclared setting '{referenced}'"
                    )


def _field_type_and_values(
    name: str,
    field: FieldInfo,
    metadata: Mapping[str, object],
) -> tuple[str, list[dict[str, object]] | None]:
    annotation, _ = _unwrap_optional(field.annotation)
    configured_values = _metadata_list(metadata, "values")
    if configured_values:
        expected_type = _scalar_annotation_type(name, annotation)
        if expected_type is bool:
            raise SettingsDeclarationError(
                f"field '{name}' cannot use boolean values as dropdown choices"
            )
        for option in configured_values:
            if type(option["value"]) is not expected_type:
                raise SettingsDeclarationError(
                    f"field '{name}' has a dropdown value that does not match its type"
                )
        return "dropdown", configured_values

    if get_origin(annotation) is Literal:
        literal_values = list(get_args(annotation))
        if not literal_values or any(type(value) not in {int, str} for value in literal_values):
            raise SettingsDeclarationError(
                f"field '{name}' must use only string or integer literal values"
            )
        literal_types = {type(value) for value in literal_values}
        if len(literal_types) != 1:
            raise SettingsDeclarationError(
                f"field '{name}' cannot mix string and integer literal values"
            )
        return "dropdown", [{"label": str(value), "value": value} for value in literal_values]

    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return "dropdown", [
            {
                "label": member.name.replace("_", " ").title(),
                "value": member.value,
            }
            for member in annotation
        ]

    scalar_type = _scalar_annotation_type(name, annotation)
    return {bool: "boolean", int: "number", str: "text"}[scalar_type], None


def _scalar_annotation_type(name: str, annotation: object) -> type[bool] | type[int] | type[str]:
    if annotation is bool:
        return bool
    if annotation is int:
        return int
    if annotation is str:
        return str
    raise SettingsDeclarationError(
        f"field '{name}' has unsupported type '{_annotation_name(annotation)}'"
    )


def _unwrap_optional(annotation: object) -> tuple[object, bool]:
    if get_origin(annotation) not in {UnionType, Union}:
        return annotation, False
    arguments = get_args(annotation)
    non_null = tuple(argument for argument in arguments if argument is not type(None))
    if len(non_null) == 1 and len(non_null) != len(arguments):
        return non_null[0], True
    return annotation, False


def _field_validators(
    field: FieldInfo,
    metadata: Mapping[str, object],
) -> list[dict[str, object]]:
    explicit = _metadata_list(metadata, "validators")
    explicit_types = {validator["type"] for validator in explicit}
    automatic: list[dict[str, object]] = []
    constraints: dict[str, object] = {}
    for constraint in field.metadata:
        if getattr(constraint, "ge", None) is not None:
            constraints["min"] = constraint.ge
        if getattr(constraint, "le", None) is not None:
            constraints["max"] = constraint.le
        if getattr(constraint, "pattern", None) is not None:
            constraints["regex"] = constraint.pattern
    for validator_type in ("min", "max", "regex"):
        if validator_type in constraints and validator_type not in explicit_types:
            automatic.append({"type": validator_type, "value": constraints[validator_type]})
    return [*automatic, *explicit]


def _normalize_dropdown_values(
    values: Sequence[DropdownValue | tuple[str, DropdownScalar] | DropdownScalar] | None,
) -> list[dict[str, object]]:
    if values is None:
        return []
    normalized: list[dict[str, object]] = []
    for option in values:
        if isinstance(option, DropdownValue):
            label, value = option.label, option.value
        elif isinstance(option, tuple) and len(option) == 2 and isinstance(option[0], str):
            label, value = option
        else:
            label, value = str(option), option
        if type(value) not in {int, str}:
            raise SettingsDeclarationError("dropdown values must be strings or integers")
        normalized.append({"label": label, "value": value})
    if len({option["value"] for option in normalized}) != len(normalized):
        raise SettingsDeclarationError("dropdown values must be unique")
    return normalized


def _normalize_validator(
    validator: SettingsValidator | Mapping[str, object],
) -> dict[str, object]:
    validator_type: object
    message: object
    if isinstance(validator, SettingsValidator):
        validator_type = validator.type
        value = validator.value
        message = validator.message
    else:
        validator_type = validator.get("type")
        value = validator.get("value")
        message = validator.get("message")
    if validator_type not in _VALIDATOR_TYPES:
        raise SettingsDeclarationError(f"unknown settings validator '{validator_type}'")
    if message is not None and not isinstance(message, str):
        raise SettingsDeclarationError("settings validator message must be a string")
    normalized: dict[str, object] = {"type": validator_type, "value": _wire_value(value)}
    if message is not None:
        normalized["message"] = message
    return normalized


def _normalize_condition(
    condition: FieldCondition | ModelCondition | ConditionGroup | Mapping[str, object],
) -> dict[str, object]:
    if isinstance(condition, FieldCondition):
        if condition.operator not in _FIELD_OPERATORS:
            raise SettingsDeclarationError(
                f"unknown field condition operator '{condition.operator}'"
            )
        return {
            "type": "field",
            "body": {
                "field": condition.field,
                "operator": condition.operator,
                "value": _wire_value(condition.value),
            },
        }
    if isinstance(condition, ModelCondition):
        allowed = _MODEL_OPERATORS.get(condition.field)
        if allowed is None or condition.operator not in allowed:
            raise SettingsDeclarationError(
                f"operator '{condition.operator}' is invalid for model field '{condition.field}'"
            )
        return {
            "type": "model",
            "body": {
                "field": condition.field,
                "operator": condition.operator,
                "value": _wire_value(condition.value),
            },
        }
    if isinstance(condition, ConditionGroup):
        if not condition.conditions:
            raise SettingsDeclarationError("a condition group cannot be empty")
        return {
            "type": "field",
            "body": [_normalize_condition_item(item) for item in condition.conditions],
        }

    condition_type = condition.get("type")
    body = condition.get("body")
    if condition_type not in {"field", "model"}:
        raise SettingsDeclarationError(f"unknown settings condition type '{condition_type}'")
    if isinstance(body, list | tuple):
        if not body:
            raise SettingsDeclarationError("a condition group cannot be empty")
        return {
            "type": condition_type,
            "body": [_normalize_condition_item(item) for item in body],
        }
    if not isinstance(body, Mapping):
        raise SettingsDeclarationError("settings condition body must be an object or a list")
    field = body.get("field")
    operator = body.get("operator")
    value = body.get("value")
    if not isinstance(field, str) or not isinstance(operator, str):
        raise SettingsDeclarationError("settings condition requires a field and operator")
    if condition_type == "field":
        return _normalize_condition(
            FieldCondition(field=field, operator=cast(FieldOperator, operator), value=value)
        )
    return _normalize_condition(
        ModelCondition(
            field=cast(ModelField, field),
            operator=cast(ModelOperator, operator),
            value=value,
        )
    )


def _normalize_condition_item(item: object) -> dict[str, object]:
    if isinstance(item, FieldCondition | ModelCondition | ConditionGroup | Mapping):
        return _normalize_condition(item)
    raise SettingsDeclarationError("condition groups may contain only conditions")


def _condition_field_references(condition: Mapping[str, object]) -> list[str]:
    body = condition.get("body")
    if isinstance(body, list):
        references: list[str] = []
        for nested in body:
            if isinstance(nested, Mapping):
                references.extend(_condition_field_references(nested))
        return references
    if condition.get("type") != "field" or not isinstance(body, Mapping):
        return []
    field = body.get("field")
    return [field] if isinstance(field, str) else []


def _setting_metadata(field: FieldInfo) -> Mapping[str, object]:
    extra = field.json_schema_extra
    if not isinstance(extra, Mapping):
        return {}
    metadata = extra.get(_METADATA_KEY)
    return metadata if isinstance(metadata, Mapping) else {}


def _metadata_list(
    metadata: Mapping[str, object],
    key: str,
) -> list[dict[str, object]]:
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item.copy()) for item in value if isinstance(item, dict)]


def _validator_accepts(value: object, validator: Mapping[str, object]) -> bool:
    validator_type = validator["type"]
    expected = validator.get("value")
    try:
        if validator_type == "min":
            return bool(value >= expected)  # type: ignore[operator]
        if validator_type == "max":
            return bool(value <= expected)  # type: ignore[operator]
        if validator_type == "regex":
            return (
                isinstance(value, str)
                and isinstance(expected, str)
                and re.search(expected, value) is not None
            )
        if validator_type == "equal":
            return value == expected
        if validator_type == "notEqual":
            return value != expected
        if validator_type == "in":
            return isinstance(expected, list | tuple | set | frozenset) and value in expected
    except TypeError, ValueError:
        return False
    return False


def _settings_error(
    error: ValidationError,
    settings_type: type[DeploymentSettings],
) -> tuple[str, str]:
    detail = cast(dict[str, object], error.errors(include_url=False)[0])
    location = detail.get("loc")
    location_parts = location if isinstance(location, tuple) else ()
    field = next(
        (str(part) for part in location_parts if str(part) in settings_type.model_fields),
        "settings",
    )
    message = str(detail.get("msg", "invalid value"))
    if field == "settings":
        field = next(
            (name for name in settings_type.model_fields if f"{name}:" in message),
            field,
        )
    return field, message


def _wire_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _wire_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_wire_value(item) for item in value]
    return value


def _annotation_name(annotation: object) -> str:
    return getattr(annotation, "__name__", str(annotation))
