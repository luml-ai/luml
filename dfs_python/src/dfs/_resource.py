from __future__ import annotations
from typing import Any, TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from ._client import DataForceClient


class APIResource:
    _client: DataForceClient

    def __init__(self, client: DataForceClient) -> None:
        self._client = client

    async def _get(self, url: str, **kwargs) -> Any:
        return await self._client.request("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs) -> Any:
        return await self._client.request("POST", url, **kwargs)

    async def _put(self, url: str, **kwargs) -> Any:
        return await self._client.request("PUT", url, **kwargs)

    async def _patch(self, url: str, **kwargs) -> Any:
        return await self._client.request("PATCH", url, **kwargs)

    async def _delete(self, url: str, **kwargs) -> Any:
        return await self._client.request("DELETE", url, **kwargs)

    async def _sleep(self, seconds: float) -> None:
        await anyio.sleep(seconds)

    def _filter_none(self, data: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in data.items() if value is not None}
