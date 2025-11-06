import logging
from collections.abc import Awaitable, Callable
from typing import Any

from openapi_generator import OpenAPIGenerator
from services.base_service import UvicornBaseService

logger = logging.getLogger(__name__)


class UvicornService(UvicornBaseService):
    def __init__(
        self,
        *,
        title: str = "Model API",
        description: str = "API for running inference on FNNX / DFS models",
        version: str = "1.0.0",
        openapi_generator: OpenAPIGenerator | None = None,
    ) -> None:
        super().__init__(title=title, description=description, version=version)

        if openapi_generator:
            self.openapi = openapi_generator
        else:
            self.openapi = OpenAPIGenerator(title=title, version=version, description=description)

        self._add_builtin_endpoints()

    def _add_builtin_endpoints(self) -> None:
        async def openapi_handler(
            service: "UvicornService",
            scope: dict[str, Any],  # noqa: ANN401
            receive: Callable[[], Awaitable[dict[str, Any]]],  # noqa: ANN401
            send: Callable[[dict[str, Any]], Awaitable[None]],  # noqa: ANN401
        ) -> None:
            schema = self.openapi.get_openapi_schema()
            await service.send_json(send, schema)

        self.routes[("/openapi.json", "GET")] = openapi_handler

        self.route_metadata[("/openapi.json", "GET")] = {
            "summary": "OpenAPI Schema",
            "description": "Returns the OpenAPI specification",
            "tags": ["documentation"],
            "function": openapi_handler,
        }
