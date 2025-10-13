import inspect
import json
from collections.abc import Awaitable, Callable
from typing import Any


class HTTPException(Exception):
    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Model API error.",
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.detail)


class UvicornBaseService:
    def __init__(
        self,
        *,
        title: str = "Uvicorn Service",
        description: str = "Uvicorn Service",
        version: str = "1.0.0",
    ) -> None:
        self.title = title
        self.description = description
        self.version = version

        self.routes: dict[tuple, Callable] = {}
        self.route_metadata: dict[tuple, dict[str, Any]] = {}  # noqa: ANN401

    def get(
        self,
        path: str,
        *,
        summary: str = None,
        description: str = None,
        response_model: type = None,
        tags: list = None,
    ) -> Any:  # noqa: ANN401
        def decorator(func: Callable) -> Callable:
            async def wrapper(
                service: "UvicornBaseService",
                scope: dict[str, Any],  # noqa: ANN401
                receive: Callable[[], Awaitable[dict[str, Any]]],  # noqa: ANN401
                send: Callable[[dict[str, Any]], Awaitable[None]],  # noqa: ANN401
            ) -> None:
                try:
                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())

                    if len(param_names) == 0:
                        result = await func()
                    elif len(param_names) == 1:
                        if param_names[0] == "scope":
                            result = await func(scope)
                        else:
                            result = await func(service)
                    else:
                        result = await func(service, send)
                        return
                    if result is not None:
                        await service.send_json(send, result)
                except HTTPException as e:
                    await service.send_json(send, {"error": e.detail}, e.status_code)
                except Exception as e:
                    await service.send_json(send, {"error": str(e)}, 500)

            self.routes[(path, "GET")] = wrapper

            self.route_metadata[(path, "GET")] = {
                "summary": summary or f"GET {path}",
                "description": description or func.__doc__,
                "response_model": response_model,
                "tags": tags or [],
                "function": func,
            }
            return wrapper

        return decorator

    def post(
        self,
        path: str,
        *,
        summary: str = None,
        description: str = None,
        request_model: type = None,
        response_model: type = None,
        tags: list = None,
    ) -> Any:  # noqa: ANN401
        def decorator(func: Callable) -> Callable:
            async def wrapper(
                service: "UvicornBaseService",
                scope: dict[str, Any],  # noqa: ANN401
                receive: Callable[[], Awaitable[dict[str, Any]]],  # noqa: ANN401
                send: Callable[[dict[str, Any]], Awaitable[None]],  # noqa: ANN401
            ) -> None:
                try:
                    body = await service._read_body(receive)
                    request_data = json.loads(body) if body else {}

                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())

                    if len(param_names) == 0:
                        result = await func()
                    elif len(param_names) == 1:
                        if param_names[0] == "request_data":
                            result = await func(request_data)
                        elif param_names[0] == "scope":
                            result = await func(scope)
                        else:
                            result = await func(service)
                    elif len(param_names) == 2:
                        if "scope" in param_names and "request_data" in param_names:
                            result = await func(scope, request_data)
                        else:
                            result = await func(service, request_data)
                    else:
                        result = await func(service, request_data)

                    if result is not None:
                        await service.send_json(send, result)

                except HTTPException as e:
                    await service.send_json(send, {"error": e.detail}, e.status_code)
                except Exception as e:
                    await service.send_json(send, {"error": str(e)}, 500)

            self.routes[(path, "POST")] = wrapper

            self.route_metadata[(path, "POST")] = {
                "summary": summary or f"POST {path}",
                "description": description or func.__doc__,
                "request_model": request_model,
                "response_model": response_model,
                "tags": tags or [],
                "function": func,
            }
            return wrapper

        return decorator

    @staticmethod
    async def send_html(
        send: Callable[[dict[str, Any]], Awaitable[None]],
        html: str,
        status: int = 200,  # noqa: ANN401
    ) -> None:
        body = html.encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"text/html"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    @staticmethod
    async def _read_body(receive: Callable[[], Awaitable[dict[str, Any]]]) -> str:  # noqa: ANN401
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
        return body.decode()

    @staticmethod
    async def send_json(
        send: Callable[[dict[str, Any]], Awaitable[None]],
        data: dict[str, Any],
        status: int = 200,  # noqa: ANN401
    ) -> None:
        body = json.dumps(data).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )

    async def _send_404(self, send: Callable[[dict[str, Any]], Awaitable[None]]) -> None:  # noqa: ANN401
        await self.send_json(send, {"error": "Not found"}, 404)

    async def __call__(
        self,
        scope: dict[str, Any],  # noqa: ANN401
        receive: Callable[[], Awaitable[dict[str, Any]]],  # noqa: ANN401
        send: Callable[[dict[str, Any]], Awaitable[None]],  # noqa: ANN401
    ) -> None:
        assert scope["type"] == "http"

        path = scope["path"]
        method = scope["method"]

        route_key = (path, method)
        if route_key in self.routes:
            handler = self.routes[route_key]
            try:
                await handler(self, scope, receive, send)
            except HTTPException as e:
                await self.send_json(send, {"error": e.detail}, e.status_code)
            except Exception as e:
                await self.send_json(send, {"error": str(e)}, 500)
        else:
            await self._send_404(send)
