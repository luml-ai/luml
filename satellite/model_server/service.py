import json
import inspect
import logging
from typing import Any, Callable, Type
from handers.model_handler import ModelHandler
from handers.openapi_generator import OpenAPIGenerator
from auth import HTTPException

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UvicornService:
    def __init__(
        self,
        *,
        title: str = "Model API",
        description: str = "API for running inference on FNNX / DFS models",
        version: str = "1.0.0",
    ) -> None:
        self.title = title
        self.description = description
        self.version = version

        logger.info("Initializing UvicornService")

        try:
            logger.info("Creating ModelHandler...")
            self.model_handler = ModelHandler()
            self.openapi = OpenAPIGenerator(self.model_handler)
            logger.info("ModelHandler created successfully")
        except Exception as e:
            logger.error(f"Failed to create ModelHandler: {e}")
            # Create a dummy handler that always returns errors
            self.model_handler = None
            self.openapi = None

        self.routes: dict[tuple, Callable] = {}
        self.route_metadata: dict[tuple, dict[str, Any]] = {}
        self._add_builtin_endpoints()

    def get(
        self,
        path: str,
        *,
        summary: str = None,
        description: str = None,
        response_model: Type = None,
        tags: list = None,
    ):
        def decorator(func):
            async def wrapper(service, scope, receive, send):
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
                        await service._send_json(send, result)
                except HTTPException as e:
                    await service._send_json(send, {"error": e.detail}, e.status_code)
                except Exception as e:
                    await service._send_json(send, {"error": str(e)}, 500)

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
        request_model: Type = None,
        response_model: Type = None,
        tags: list = None,
    ):
        def decorator(func):
            async def wrapper(service, scope, receive, send):
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
                        await service._send_json(send, result)
                except HTTPException as e:
                    await service._send_json(send, {"error": e.detail}, e.status_code)
                except Exception as e:
                    await service._send_json(send, {"error": str(e)}, 500)

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

    def generate_openapi_schema(self) -> dict[str, Any]:
        return self.openapi.get_openapi_schema(
            title=self.title,
            version=self.version,
            description=self.description,
        )

    @staticmethod
    async def _send_html(send, html: str, status: int = 200):
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
    async def _read_body(receive) -> str:
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                if not message.get("more_body", False):
                    break
        return body.decode()

    @staticmethod
    async def _send_json(send, data: dict[str, Any], status: int = 200):
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

    async def _send_404(self, send):
        await self._send_json(send, {"error": "Not found"}, 404)

    def _add_builtin_endpoints(self):
        async def docs_handler(service, scope, receive, send):
            if service.openapi is None:
                await service._send_json(
                    send,
                    {
                        "error": "ModelHandler initialization failed. Check logs and environment variables."
                    },
                    500,
                )
                return
            await service._send_html(send, service.openapi.openapi_html())

        async def openapi_handler(service, scope, receive, send):
            if service.openapi is None:
                await service._send_json(
                    send,
                    {
                        "error": "ModelHandler initialization failed. Check logs and environment variables."
                    },
                    500,
                )
                return
            schema = service.generate_openapi_schema()
            await service._send_json(send, schema)

        self.routes[("/docs", "GET")] = docs_handler
        self.routes[("/openapi.json", "GET")] = openapi_handler

        self.route_metadata[("/docs", "GET")] = {
            "summary": "Swagger UI Documentation",
            "description": "Interactive API documentation",
            "tags": ["documentation"],
            "function": docs_handler,
        }

        self.route_metadata[("/openapi.json", "GET")] = {
            "summary": "OpenAPI Schema",
            "description": "Returns the OpenAPI specification",
            "tags": ["documentation"],
            "function": openapi_handler,
        }

    async def __call__(self, scope: dict[str, Any], receive, send):
        assert scope["type"] == "http"

        path = scope["path"]
        method = scope["method"]

        route_key = (path, method)
        if route_key in self.routes:
            handler = self.routes[route_key]
            try:
                await handler(self, scope, receive, send)
            except HTTPException as e:
                await self._send_json(send, {"error": e.detail}, e.status_code)
            except Exception as e:
                await self._send_json(send, {"error": str(e)}, 500)
        else:
            await self._send_404(send)
