from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from agent.handlers.model_server_handler import ModelServerHandler, HttpClient
from agent.schemas.endpoints import (
    DeploymentInfo,
    DocsUrl,
    Healthz,
    InferenceAccessIn,
    InferenceAccessOut,
)
from fastapi import FastAPI, HTTPException

model_server_handler = ModelServerHandler()
httpx_client = HttpClient()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    await model_server_handler.sync_deployments()

    yield

    # await model_server_handler.shutdown()


def create_agent_app(authorize_access: Callable[[str], Awaitable[bool]]) -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.post("/satellites/deployments/inference-access", response_model=InferenceAccessOut)
    async def authorize_inference_access(body: InferenceAccessIn) -> InferenceAccessOut:  # noqa: D401
        try:
            authorized = bool(await authorize_access(body.api_key))
            return InferenceAccessOut(authorized=authorized)
        except Exception as err:
            raise HTTPException(status_code=502, detail="Authorization check failed") from err

    @app.get("/healthz", response_model=Healthz)
    def healthz() -> dict:
        return {"status": "healthy"}

    @app.get("/deployments", response_model=list[DeploymentInfo])
    async def deployments() -> list[dict]:
        return await model_server_handler.list_active_deployments()

    @app.post("/deployments/{deployment_id}/compute", response_model=dict)
    async def compute(deployment_id: int, body: dict) -> dict:
        try:
            return await model_server_handler.model_compute(deployment_id, body)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Compute failed: {str(e)}") from e

    @app.get("/deployments/{deployment_id}/manifest", response_model=dict)
    async def manifest(deployment_id: int) -> dict:
        try:
            return await model_server_handler.model_manifest(deployment_id)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Manifest retrieval failed: {str(e)}"
            ) from e

    @app.get("/deployments/{deployment_id}/docs-url", response_model=DocsUrl)
    async def model_docs_url(deployment_id: int) -> dict:
        try:
            deployment = await model_server_handler.get_deployment(str(deployment_id))
            if not deployment:
                raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
            return {"url": f"{deployment['model_url']}/docs"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get docs URL: {str(e)}") from e

    @app.get("/deployments/{deployment_id}/healthz", response_model=Healthz)
    async def model_healthz(deployment_id: int) -> dict:
        try:
            deployment = await model_server_handler.get_deployment(str(deployment_id))
            if not deployment:
                raise HTTPException(status_code=404, detail=f"Deployment {deployment_id} not found")
            return await httpx_client.get(f"{deployment['model_url']}/healthz")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    return app
