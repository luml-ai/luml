from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agent.handlers.handler_instances import ms_handler
from agent.handlers.openapi_handler import OpenAPIHandler
from agent.schemas import (
    DeploymentInfo,
    InferenceAccessIn,
    InferenceAccessOut,
)

openapi_handler = OpenAPIHandler(ms_handler)


class OpenAPISchemaBuilder:
    @staticmethod
    def generate_base_schema(app: FastAPI) -> dict[str, Any]:
        return get_openapi(
            title="Satellite Agent API",
            version="1.0.0",
            description="API for managing model deployments and inference",
            routes=app.routes,
        )

    @staticmethod
    def add_security_to_schema(openapi_schema: dict[str, Any]) -> None:
        for path_data in openapi_schema.get("paths", {}).values():
            for method_data in path_data.values():
                if isinstance(method_data, dict):
                    method_data["security"] = [{"HTTPBearer": []}]

        if "components" not in openapi_schema:
            openapi_schema["components"] = {}

        openapi_schema["components"]["securitySchemes"] = {
            "HTTPBearer": {"type": "http", "scheme": "bearer"}
        }


def create_deploy_router(authorize_access: Callable[[str], Awaitable[bool]]) -> APIRouter:
    router = APIRouter()
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
            raise HTTPException(status_code=502, detail="Authorization failed") from error

    @router.post("/satellites/deployments/inference-access", response_model=InferenceAccessOut)
    async def authorize_inference_access(body: InferenceAccessIn) -> InferenceAccessOut:  # noqa: D401
        try:
            authorized = bool(await authorize_access(body.api_key))
            return InferenceAccessOut(authorized=authorized)
        except Exception as err:
            raise HTTPException(
                status_code=502, detail=f"Authorization check failed: {str(err)}"
            ) from err

    @router.get("/deployments", response_model=list[DeploymentInfo])
    async def deployments(authorized: bool = Depends(verify_token)) -> list[dict]:  # noqa: B008
        local_deployments = await ms_handler.list_active_deployments()
        return [{"deployment_id": deployment.deployment_id} for deployment in local_deployments]

    @router.post("/deployments/{deployment_id}/compute", response_model=dict)
    async def compute(
        deployment_id: str,
        body: dict,
        authorized: bool = Depends(verify_token),  # noqa: B008
    ) -> dict:
        try:
            return await ms_handler.model_compute(deployment_id, body)
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"Compute failed: {str(error)}") from error

    return router


def setup_custom_openapi(app: FastAPI) -> None:
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

    app.openapi = custom_openapi
