import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.openapi.utils import get_openapi

from agent.handlers.handler_instances import ms_handler, secrets_handler
from agent.schemas.deployments import (
    DeploymentInfo,
    Healthz,
    InferenceAccessIn,
    InferenceAccessOut,
)
from .handlers.openapi_handler import OpenAPIHandler

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
            "HTTPBearer": {
                "type": "http",
                "scheme": "bearer"
            }
        }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    asyncio.create_task(ms_handler.sync_deployments())
    asyncio.create_task(secrets_handler.initialize())

    yield

    # await model_server_handler.shutdown()


def create_agent_app(authorize_access: Callable[[str], Awaitable[bool]]) -> FastAPI:
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
            raise HTTPException(status_code=502, detail="Authorization failed") from error

    @app.post("/satellites/deployments/inference-access", response_model=InferenceAccessOut)
    async def authorize_inference_access(body: InferenceAccessIn) -> InferenceAccessOut:  # noqa: D401
        try:
            authorized = bool(await authorize_access(body.api_key))
            return InferenceAccessOut(authorized=authorized)
        except Exception as err:
            raise HTTPException(
                status_code=502, detail=f"Authorization check failed: {str(err)}"
            ) from err

    @app.get("/healthz", response_model=Healthz)
    def healthz() -> dict:
        return {"status": "healthy"}

    @app.get("/deployments", response_model=list[DeploymentInfo])
    async def deployments(authorized: bool = Depends(verify_token)) -> list[dict]:  # noqa: B008
        local_deployments = await ms_handler.list_active_deployments()
        return [{"deployment_id": deployment.deployment_id} for deployment in local_deployments]

    @app.post("/deployments/{deployment_id}/compute", response_model=dict)
    async def compute(
        deployment_id: int, body: dict, authorized: bool = Depends(verify_token)  # noqa: B008
    ) -> dict:
        try:
            return await ms_handler.model_compute(deployment_id, body)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Compute failed: {str(e)}") from e

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        builder = OpenAPISchemaBuilder()
        openapi_schema = builder.generate_base_schema(app)
        builder.add_security_to_schema(openapi_schema)

        app.openapi_schema = openapi_handler.merge_deployment_schemas(openapi_schema)
        return app.openapi_schema

    def invalidate_openapi_cache():
        app.openapi_schema = None
    
    ms_handler.register_openapi_cache_invalidation_callback(invalidate_openapi_cache)
    
    app.openapi = custom_openapi
    return app
