import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from .._exceptions import ConfigurationError


def validate_organization(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        organization_id: int | None = None,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if organization_id is None and not self._client.organization:
            raise ConfigurationError(
                "organization_id must be provided or default organization must be set"
            )

        result = func(
            self,
            organization_id=organization_id or self._client.organization,
            *args,  # noqa: B026
            **kwargs,
        )
        if asyncio.iscoroutine(result):
            return result
        return result

    return wrapper


def validate_organization_orbit(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        organization_id: int | None = None,
        orbit_id: int | None = None,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if organization_id is None and not self._client.organization:
            raise ConfigurationError(
                "organization_id must be provided or default organization must be set"
            )
        if orbit_id is None and not self._client.orbit:
            raise ConfigurationError(
                "orbit_id must be provided or default orbit must be set"
            )

        result = func(
            self,
            organization_id=organization_id or self._client.organization,
            orbit_id=orbit_id or self._client.orbit,
            *args,  # noqa: B026
            **kwargs,
        )
        if asyncio.iscoroutine(result):
            return result
        return result

    return wrapper


def validate_organization_orbit_collection(
    func: Callable[..., Any],
) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(
        self: Any,  # noqa: ANN401
        organization_id: int | None = None,
        orbit_id: int | None = None,
        collection_id: int | None = None,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if organization_id is None and not self._client.organization:
            raise ConfigurationError(
                "organization_id must be provided or default organization must be set"
            )
        if orbit_id is None and not self._client.orbit:
            raise ConfigurationError(
                "orbit_id must be provided or default orbit must be set"
            )
        if collection_id is None and not self._client.collection:
            raise ConfigurationError(
                "collection_id must be provided or default collection must be set"
            )

        result = func(
            self,
            organization_id=organization_id or self._client.organization,
            orbit_id=orbit_id or self._client.orbit,
            collection_id=collection_id or self._client.collection,
            *args,  # noqa: B026
            **kwargs,
        )
        if asyncio.iscoroutine(result):
            return result
        return result

    return wrapper
