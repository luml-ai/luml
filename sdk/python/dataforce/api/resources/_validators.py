import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from .._exceptions import ConfigurationError


def validate_collection(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        collection_id: int | None = None,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if not self._client.organization:
            raise ConfigurationError("Default organization must be set")
        if not self._client.orbit:
            raise ConfigurationError("Default orbit must be set")
        if collection_id is None and not self._client.collection:
            raise ConfigurationError(
                "collection_id must be provided or default collection must be set"
            )

        result = func(
            self,
            collection_id=collection_id or self._client.collection,
            *args,  # noqa: B026
            **kwargs,
        )
        if asyncio.iscoroutine(result):
            return result
        return result

    return wrapper
