import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from .._exceptions import ConfigurationError


def validate_collection(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to validate and autofill collection_id parameter.

    Ensures organization, orbit, and collection are configured before method execution.
    If collection_id is None, uses default collection from client.

    Raises:
        ConfigurationError: In the following cases:
            - Default organization is not set in client
            - Default orbit is not set in client
            - collection_id parameter is None AND default collection
                is not set in client
    """

    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if not self._client.organization:
            raise ConfigurationError(
                "Organization",
                "Default organization must be set",
                all_values=self._client.organizations.list(),
            )
        if not self._client.orbit:
            raise ConfigurationError(
                "Orbit",
                "Default orbit must be set",
                all_values=self._client.orbits.list(),
            )

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
