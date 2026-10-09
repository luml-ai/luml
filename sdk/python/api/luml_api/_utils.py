from collections.abc import Callable

from luml_api._exceptions import MultipleResourcesFoundError


def find_by_value[T](
    items: list[T], value: str, condition: Callable[[T], bool] | None = None
) -> T | None:
    condition = condition or (lambda item: getattr(item, "name", None) == value)

    matches = [item for item in items if condition(item)]

    if len(matches) > 1:
        raise MultipleResourcesFoundError(
            f"Multiple items found with name or id '{value}'. "
        )

    return matches[0] if matches else None
