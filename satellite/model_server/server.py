import logging
from typing import Any

from pydantic import ValidationError
from services.base_service import HTTPException
from services.service import UvicornService

app = UvicornService()


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger("satellite")


@app.get(
    "/healthz",
    summary="Health Check",
    description="Returns the health status of the service",
    tags=["model"],
)
async def healthz() -> dict[str, str]:
    return {"status": "healthy"}


@app.get(
    "/manifest",
    summary="Get Model Manifest",
    description="Returns the FNNX model manifest with input/output specifications",
    tags=["model"],
)
async def get_manifest() -> dict[str, Any]:  # noqa: ANN401
    try:
        return app.model_handler.get_manifest()
    except Exception as error:
        return {"error": f"Failed to get manifest: {str(error)}"}


@app.post(
    "/compute",
    summary="Run Model Inference",
    description="Execute inference on the loaded model",
    response_model=dict[str, Any],  # noqa: ANN401
    tags=["model"],
)
async def compute(request_data: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN401
    ComputeRequest = app.model_handler.get_request_model()
    try:
        validated_request = ComputeRequest(**request_data)
    except ValidationError as error:
        logger.error(f"Input validation failed: {error}")
        raise HTTPException(status_code=422, detail=f"Input validation failed: {error}") from error
    except Exception as error:
        logger.error(f"Validation error: {error}")
        raise HTTPException(status_code=422, detail=f"Validation error: {error}") from error

    try:
        result = await app.model_handler.compute_result(
            validated_request.inputs, validated_request.dynamic_attributes
        )
        return result
    except Exception as error:
        logger.error(f"Model computation failed: {error}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Model computation failed: {error}") from error


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=6005)
