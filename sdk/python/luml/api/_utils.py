from collections.abc import Callable
from typing import TypeVar

from ._exceptions import MultipleResourcesFoundError

T = TypeVar("T")


def find_by_value(
    items: list[T], value: str, condition: Callable[[T], bool] | None = None
) -> T | None:
    condition = condition or (lambda item: getattr(item, "name", None) == value)

    matches = [item for item in items if condition(item)]

    if len(matches) > 1:
        raise MultipleResourcesFoundError(
            f"Multiple items found with name or id '{value}'. "
        )

    return matches[0] if matches else None
