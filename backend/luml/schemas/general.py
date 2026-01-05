from datetime import datetime
from enum import StrEnum


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


type CursorType = int | str | float | datetime
