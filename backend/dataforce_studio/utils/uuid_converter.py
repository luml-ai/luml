from uuid import UUID, uuid4

import shortuuid


class UUIDConverter:
    @staticmethod
    def generate_uuid_pair() -> tuple[str, str]:
        full_uuid = str(uuid4())
        return full_uuid, shortuuid.encode(UUID(full_uuid))

    @staticmethod
    def uuid_to_short(full_uuid: str | UUID) -> str:
        if isinstance(full_uuid, UUID):
            full_uuid = str(full_uuid)
        return shortuuid.encode(UUID(full_uuid))

    @staticmethod
    def short_to_uuid(short_uuid: str | UUID) -> str:
        if isinstance(short_uuid, UUID):
            return str(short_uuid)
        if UUIDConverter.is_valid_uuid(short_uuid):
            return short_uuid
        return str(shortuuid.decode(short_uuid))

    @staticmethod
    def is_valid_short_uuid(value: str | UUID) -> bool:
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
    def is_valid_uuid(value: str | UUID) -> bool:
        try:
            if isinstance(value, UUID):
                return True
            if isinstance(value, str):
                UUID(value)
                return True
            return False
        except (ValueError, TypeError):
            return False
