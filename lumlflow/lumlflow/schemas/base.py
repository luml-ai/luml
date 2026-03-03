from enum import StrEnum

from pydantic import (
    ConfigDict,
)


class BaseOrmConfig:
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
