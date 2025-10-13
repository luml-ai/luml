import logging
from collections.abc import Awaitable, Callable
from typing import Any

from handlers.model_handler import ModelHandler
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
    ) -> None:
        super().__init__(title=title, description=description, version=version)

        logger.info("Initializing ModelHandler...")
        try:
            self.model_handler = ModelHandler()
            self.openapi = OpenAPIGenerator(self.model_handler)
            logger.info("ModelHandler initialized successfully")
        except Exception as error:
            logger.error(f"Failed to initialize ModelHandler: {error}", exc_info=True)
            self.model_handler = None
            self.openapi = None

        self._add_builtin_endpoints()

    def generate_openapi_schema(self) -> dict[str, Any]:  # noqa: ANN401
        return self.openapi.get_openapi_schema(
            title=self.title,
            version=self.version,
            description=self.description,
        )

    def _add_builtin_endpoints(self) -> None:
        async def docs_handler(
            service: "UvicornService",
            scope: dict[str, Any],  # noqa: ANN401
            receive: Callable[[], Awaitable[dict[str, Any]]],  # noqa: ANN401
            send: Callable[[dict[str, Any]], Awaitable[None]],  # noqa: ANN401
        ) -> None:
            if service.openapi is None:
                await service.send_json(send, {"error": "ModelHandler initialization failed."}, 500)
                return
            await service.send_html(send, service.openapi.openapi_html())

        async def openapi_handler(
            service: "UvicornService",
            scope: dict[str, Any],  # noqa: ANN401
            receive: Callable[[], Awaitable[dict[str, Any]]],  # noqa: ANN401
            send: Callable[[dict[str, Any]], Awaitable[None]],  # noqa: ANN401
        ) -> None:
            if service.openapi is None:
                await service.send_json(send, {"error": "ModelHandler initialization failed."}, 500)
                return
            schema = service.generate_openapi_schema()
            await service.send_json(send, schema)

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
