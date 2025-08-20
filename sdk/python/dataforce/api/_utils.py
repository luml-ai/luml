from collections.abc import Callable
from typing import TypeVar

from ._exceptions import MultipleResourcesFoundError

T = TypeVar("T")


def find_by_value(
    items: list[T], value: str | int, condition: Callable[[T], bool] | None = None
) -> T | None:
    """
    Find a single item in a list by value using a custom condition.

    Searches through a list of items to find exactly one match based on the provided
    condition. If no condition is provided, defaults to matching the 'name' attribute.
    Ensures uniqueness by raising an error if multiple matches are found.

    Args:
        items: List of items to search through.
        value: The value to search for (string or integer).
        condition: Optional callable that takes an item and returns True if it matches.
            If None, defaults to checking if item.name equals the value.

    Returns:
        The matching item from the list, or None if no match is found.

    Raises:
        MultipleResourcesFoundError: If more than one item matches the condition.
            This ensures data integrity by preventing ambiguous results.

    Note:
        This function is commonly used in SDK resource classes to find unique
        resources by name or ID while ensuring data consistency.
    """
    condition = condition or (lambda item: getattr(item, "name", None) == value)

    matches = [item for item in items if condition(item)]

    if len(matches) > 1:
        raise MultipleResourcesFoundError(
            f"Multiple items found with name or id '{value}'. "
        )

    return matches[0] if matches else None
