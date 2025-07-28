from typing import Any

from httpx import URL
import httpx


class BaseClient:
    _client: httpx.AsyncClient

    def __init__(
        self,
        base_url: str | URL,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    @property
    def base_url(self) -> URL:
        return self._base_url

    @base_url.setter
    def base_url(self, url: URL) -> None:
        self._base_url = url

    @property
    def auth_headers(self) -> dict[str, str]:
        return {}

    @property
    def default_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "dataforce-sdk/0.1.0",
            **self.auth_headers,
        }

    async def _process_response(self, response: httpx.Response):
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        final_headers = {**self.default_headers}
        if headers:
            final_headers.update(headers)

        response = await self._client.request(
            method=method,
            url=url,
            headers=final_headers,
            json=json,
            params=params,
            **kwargs,
        )
        return await self._process_response(response)
