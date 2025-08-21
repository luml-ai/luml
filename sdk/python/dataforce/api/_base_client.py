from abc import ABC, abstractmethod
from typing import Any

import httpx
from httpx import URL

from ._exceptions import (
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    UnprocessableEntityError,
)


class BaseClient(ABC):
    def __init__(
        self,
        base_url: str | URL,
        timeout: float = 30.0,
    ) -> None:
        self._base_url: URL = URL(base_url) if isinstance(base_url, str) else base_url
        self._timeout: float = timeout

    @property
    def base_url(self) -> URL:
        return self._base_url

    @base_url.setter
    def base_url(self, url: URL) -> None:
        self._base_url = url

    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, timeout: float) -> None:
        self._timeout = timeout

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

    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)

    @abstractmethod
    def _process_response(self, response: httpx.Response) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    @abstractmethod
    def request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    def get(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    def post(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    def patch(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    def delete(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    def put(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        raise NotImplementedError()

    def filter_none(self, data: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN401
        return {key: value for key, value in data.items() if value is not None}


class SyncBaseClient(BaseClient):
    _client: httpx.Client

    def __init__(
        self,
        base_url: str | URL,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        super().__init__(base_url=base_url, timeout=timeout)

    def _process_response(self, response: httpx.Response) -> dict | None:
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = response.text if response.content else None
            raise self._make_status_error(
                f"Error response {response.status_code} "
                f"while requesting {response.request.method} {response.url}",
                body=body,
                response=response,
            )

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        final_headers = {**self.default_headers}
        if headers:
            final_headers.update(headers)

        response = self._client.request(
            method=method,
            url=url,
            headers=final_headers,
            json=json,
            params=params,
            **kwargs,
        )
        return self._process_response(response)

    def get(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return self.request("DELETE", url, **kwargs)

    def put(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return self.request("PUT", url, **kwargs)


class AsyncBaseClient(BaseClient):
    _client: httpx.AsyncClient

    def __init__(
        self,
        base_url: str | URL,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        super().__init__(base_url=base_url, timeout=timeout)

    async def _process_response(self, response: httpx.Response) -> dict | None:
        if response.status_code >= 400:
            try:
                body = response.json()
            except Exception:
                body = response.text if response.content else None

            raise self._make_status_error(
                f"Error response {response.status_code} "
                f"while requesting {response.request.method} {response.url}",
                body=body,
                response=response,
            )

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
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
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

    async def get(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return await self.request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return await self.request("DELETE", url, **kwargs)

    async def put(self, url: str, **kwargs) -> Any:  # noqa: ANN401
        return await self.request("PUT", url, **kwargs)
