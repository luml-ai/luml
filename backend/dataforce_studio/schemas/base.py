from typing import Annotated, Any, Union
from uuid import UUID

import shortuuid
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    GetCoreSchemaHandler,
)
from pydantic_core import core_schema

from dataforce_studio.utils.uuid_converter import UUIDConverter


# def validate_short_uuid(value: str | UUID) -> str:
#     if hasattr(value, "__str__") and not isinstance(value, str):
#         value = str(value)
#
#     if isinstance(value, str):
#         if UUIDConverter.is_valid_short_uuid(value):
#             return str(UUIDConverter.short_to_uuid(value))
#         if UUIDConverter.is_valid_uuid(value):
#             return value
#         raise ValueError(f"Invalid UUID format: {value}")
#
#     raise ValueError(f"Invalid UUID format: {value}")
#
#
# def serialize_to_short_uuid(value: str | UUID) -> str:
#     if hasattr(value, "__str__") and not isinstance(value, str):
#         value = str(value)
#
#     if isinstance(value, str) and UUIDConverter.is_valid_uuid(value):
#         return UUIDConverter.uuid_to_short(value)
#
#     return str(value)
#
#
# ShortUUID = Annotated[
#     str | UUID,
#     BeforeValidator(validate_short_uuid),
#     PlainSerializer(serialize_to_short_uuid, when_used="json"),
#     Field(description="ID field that accepts and returns ShortUUID format"),
# ]



class ShortUUIDMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:  # noqa: ANN401
        if type(instance) is cls:
            return True

        if isinstance(instance, str):
            return cls._is_valid_short_uuid(instance) or cls._is_valid_uuid(instance)

        return False

    @staticmethod
    def _is_valid_short_uuid(value: str | UUID) -> bool:
        try:
            if isinstance(value, UUID):
                value = str(value)
            if isinstance(value, str):
                shortuuid.decode(value)
                return True
            return False
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _is_valid_uuid(value: str | UUID) -> bool:
        try:
            if isinstance(value, UUID):
                return True
            if isinstance(value, str):
                UUID(value)
                return True
            return False
        except (ValueError, TypeError):
            return False


class ShortUUID(metaclass=ShortUUIDMeta):
    __slots__ = ("_value",)

    def __init__(self, value: Union[str, UUID, "ShortUUID"]) -> None:
        if type(value) is ShortUUID:
            self._value = value._value
        elif isinstance(value, str | UUID):
            self._value = self._validate_short_uuid(value)
        else:
            raise TypeError(
                f"ShortUUID expects str, UUID, or ShortUUID, got {type(value).__name__}"
            )

    def __str__(self) -> str:
        return self.to_short()

    def __repr__(self) -> str:
        return f"ShortUUID('{self._value}')"

    def __eq__(self, other: Any) -> bool:  # noqa: ANN401
        if type(other) is ShortUUID:
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other
        return False

    def __hash__(self) -> int:
        return hash(self._value)

    @property
    def value(self) -> str:
        return self._value

    def to_short(self) -> str:
        return self._uuid_to_short(self._value)

    def to_uuid(self) -> str:
        return self._short_to_uuid(self._value)

    @staticmethod
    def _uuid_to_short(full_uuid: Union[str, UUID, "ShortUUID"]) -> str:
        if isinstance(full_uuid, UUID):
            full_uuid = str(full_uuid)
        return shortuuid.encode(UUID(full_uuid))

    @staticmethod
    def _short_to_uuid(short_uuid: Union[str, UUID, "ShortUUID"]) -> str:
        if isinstance(short_uuid, UUID):
            return str(short_uuid)
        if ShortUUID._is_valid_uuid(short_uuid):
            return short_uuid
        return str(shortuuid.decode(short_uuid))

    @staticmethod
    def _is_valid_short_uuid(value: Union[str, UUID, "ShortUUID"]) -> bool:
        try:
            if isinstance(value, UUID):
                value = str(value)
            if isinstance(value, str):
                shortuuid.decode(value)
                return True
            return False
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _is_valid_uuid(value: Union[str, UUID, "ShortUUID"]) -> bool:
        try:
            if isinstance(value, UUID):
                return True
            if isinstance(value, str):
                UUID(value)
                return True
            return False
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _validate_short_uuid(value: Union[str, UUID, "ShortUUID"]) -> str:
        if hasattr(value, "__str__") and not isinstance(value, str):
            value = str(value)

        if isinstance(value, str):
            if ShortUUID._is_valid_short_uuid(value):
                return str(ShortUUID._short_to_uuid(value))
            if ShortUUID._is_valid_uuid(value):
                return value
            raise ValueError(f"Invalid UUID format: {value}")

        raise ValueError(f"Invalid UUID format: {value}")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,  # noqa: ANN401
    ) -> core_schema.CoreSchema:
        def validate(value: str | UUID | ShortUUID) -> ShortUUID:
            return cls(value)

        def serialize(value: ShortUUID) -> str:
            return value.to_short()

        return core_schema.with_info_plain_validator_function(
            lambda v, _: validate(v),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize,
                return_schema=core_schema.str_schema(),
                when_used="json",
            ),
        )


class BaseOrmConfig:
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
