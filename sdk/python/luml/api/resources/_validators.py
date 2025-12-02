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


def validate_organization(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        organization_value = kwargs.get("organization_value")

        if organization_value is None and not self._client.organization:
            raise ConfigurationError(
                "organization_id must be provided or default organization must be set"
            )

        kwargs["organization_value"] = organization_value or self._client.organization
        result = func(self, *args, **kwargs)
        if asyncio.iscoroutine(result):
            return result
        return result

    return wrapper
