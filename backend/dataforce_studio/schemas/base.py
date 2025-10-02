from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, ConfigDict, Field, PlainSerializer

from dataforce_studio.utils.uuid_converter import UUIDConverter



def validate_short_uuid(value: str | UUID) -> str:
    print(f'[validate_short_uuid] value {value} type {type(value)}')
    if hasattr(value, "__str__") and not isinstance(value, str):
        value = str(value)

    if isinstance(value, str):
        if UUIDConverter.is_valid_short_uuid(value):
            return str(UUIDConverter.short_to_uuid(value))
        if UUIDConverter.is_valid_uuid(value):
            return value

    raise ValueError(f"Invalid UUID format: {value}")


def serialize_to_short_uuid(value: str | UUID) -> str:
    print(f'[serialize_to_short_uuid] value {value} type {type(value)}')
    if hasattr(value, "__str__") and not isinstance(value, str):
        value = str(value)

    if isinstance(value, str) and UUIDConverter.is_valid_uuid(value):
        return UUIDConverter.uuid_to_short(value)

    return str(value)


ShortUUID = Annotated[
    str | UUID,
    BeforeValidator(validate_short_uuid),
    PlainSerializer(serialize_to_short_uuid, when_used="json"),
    Field(description="ID field that accepts and returns ShortUUID format"),
]


class BaseOrmConfig:
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
