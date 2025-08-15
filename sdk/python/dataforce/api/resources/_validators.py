import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from .._exceptions import ConfigurationError


def validate_collection(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if not self._client.organization:
            raise ConfigurationError("Default organization must be set")
        if not self._client.orbit:
            raise ConfigurationError("Default orbit must be set")

        # collection_id is now always in kwargs (keyword-only parameter)
        collection_id = kwargs.get("collection_id")

        if collection_id is None and not self._client.collection:
            raise ConfigurationError(
                "collection_id must be provided or default collection must be set"
            )

        kwargs["collection_id"] = collection_id or self._client.collection
        result = func(self, *args, **kwargs)
        if asyncio.iscoroutine(result):
            return result
        return result

    return wrapper
