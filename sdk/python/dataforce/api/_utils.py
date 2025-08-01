from collections.abc import Callable
from typing import TypeVar

from ._exceptions import MultipleResourcesFoundError

T = TypeVar("T")


def find_by_name(
    items: list[T], name: str, condition: Callable[[T], bool] | None = None
) -> T | None:
    condition = condition or (lambda item: item.name == name)

    matches = [item for item in items if condition(item)]

    if len(matches) > 1:
        raise MultipleResourcesFoundError(f"Multiple items found with name '{name}'. ")

    return matches[0] if matches else None
