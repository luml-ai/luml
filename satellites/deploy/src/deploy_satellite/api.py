"""FastAPI application for the deploy satellite agent API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from deploy_satellite.model_server.handler import ModelServerHandler
from deploy_satellite.model_server.openapi_handler import OpenAPIHandler
from deploy_satellite.model_server.schemas import (
    DeploymentInfo,
    Healthz,
    InferenceAccessIn,
    InferenceAccessOut,
)


class OpenAPISchemaBuilder:
    """Builder for generating OpenAPI schemas with security configurations."""

    @staticmethod
    def generate_base_schema(app: FastAPI) -> dict[str, Any]:
        """Generate the base OpenAPI schema from the FastAPI app.

        Args:
            app: The FastAPI application.

        Returns:
            The base OpenAPI schema dictionary.
        """
        return get_openapi(
            title="Satellite Agent API",
            version="1.0.0",
            description="API for managing model deployments and inference",
            routes=app.routes,
        )

    @staticmethod
    def add_security_to_schema(openapi_schema: dict[str, Any]) -> None:
        """Add security requirements to all endpoints in the schema.

        Args:
            openapi_schema: The OpenAPI schema to modify.
        """
        for path_data in openapi_schema.get("paths", {}).values():
            for method_data in path_data.values():
                if isinstance(method_data, dict):
                    method_data["security"] = [{"HTTPBearer": []}]

        if "components" not in openapi_schema:
            openapi_schema["components"] = {}

        openapi_schema["components"]["securitySchemes"] = {
            "HTTPBearer": {"type": "http", "scheme": "bearer"}
        }


def create_agent_app(
    ms_handler: ModelServerHandler,
    authorize_access: Callable[[str], Awaitable[bool]],
    platform_url: str,
    satellite_token: str,
) -> FastAPI:
    """Create and configure the FastAPI agent application.

    Args:
        ms_handler: The model server handler instance.
        authorize_access: Async function to authorize API access.
        platform_url: The platform API URL for sync operations.
        satellite_token: The satellite authentication token.

    Returns:
        The configured FastAPI application.
    """
    openapi_handler = OpenAPIHandler(ms_handler)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        asyncio.create_task(ms_handler.sync_deployments(platform_url, satellite_token))
        yield

    app = FastAPI(lifespan=lifespan)
    security = HTTPBearer()

    async def verify_token(
        credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    ) -> bool:
        try:
            authorized = await authorize_access(credentials.credentials)
            if not authorized:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return True
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(
                status_code=502, detail="Authorization failed"
            ) from error

    @app.post(
        "/satellites/deployments/inference-access", response_model=InferenceAccessOut
    )
    async def authorize_inference_access(
        body: InferenceAccessIn,
    ) -> InferenceAccessOut:
        """Authorize inference access with an API key."""
        try:
            authorized = bool(await authorize_access(body.api_key))
            return InferenceAccessOut(authorized=authorized)
        except Exception as err:
            raise HTTPException(
                status_code=502, detail=f"Authorization check failed: {str(err)}"
            ) from err

    @app.get("/healthz", response_model=Healthz)
    def healthz() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/deployments", response_model=list[DeploymentInfo])
    async def deployments(
        authorized: bool = Depends(verify_token),  # noqa: B008
    ) -> list[dict[str, str]]:
        """List all active deployments."""
        local_deployments = await ms_handler.list_active_deployments()
        return [
            {"deployment_id": deployment.deployment_id}
            for deployment in local_deployments
        ]

    @app.post("/deployments/{deployment_id}/compute", response_model=dict)
    async def compute(
        deployment_id: str,
        body: dict[str, Any],
        authorized: bool = Depends(verify_token),  # noqa: B008
    ) -> dict[str, Any]:
        """Run inference on a deployed model."""
        try:
            return await ms_handler.model_compute(
                deployment_id, body, platform_url, satellite_token
            )
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Compute failed: {str(error)}"
            ) from error

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        builder = OpenAPISchemaBuilder()
        openapi_schema = builder.generate_base_schema(app)
        builder.add_security_to_schema(openapi_schema)

        app.openapi_schema = openapi_handler.merge_deployment_schemas(openapi_schema)
        return app.openapi_schema

    def invalidate_openapi_cache() -> None:
        app.openapi_schema = None

    ms_handler.register_openapi_cache_invalidation_callback(invalidate_openapi_cache)

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app
