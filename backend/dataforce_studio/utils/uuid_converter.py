from typing import Any
from uuid import UUID, uuid4

import shortuuid


class UUIDConverter:
    @staticmethod
    def generate_uuid_pair() -> tuple[str, str]:
        full_uuid = str(uuid4())
        return full_uuid, shortuuid.encode(UUID(full_uuid))

    @staticmethod
    def uuid_to_short(full_uuid: Any) -> str:
        if hasattr(full_uuid, "__str__") and not isinstance(full_uuid, str):
            full_uuid = str(full_uuid)
        return shortuuid.encode(UUID(full_uuid))

    @staticmethod
    def short_to_uuid(short_uuid: str) -> str:
        return str(shortuuid.decode(short_uuid))

    @staticmethod
    def is_valid_short_uuid(value: Any) -> bool:
        try:
            if hasattr(value, "__str__") and not isinstance(value, str):
                value = str(value)
            if isinstance(value, str):
                shortuuid.decode(value)
                return True
            return False
        except (ValueError, TypeError):
            return False

    @staticmethod
    def is_valid_uuid(value: Any) -> bool:
        try:
            if hasattr(value, "__str__") and not isinstance(value, str):
                value = str(value)
            if isinstance(value, str):
                UUID(value)
                return True
            return False
        except (ValueError, TypeError):
            return False
