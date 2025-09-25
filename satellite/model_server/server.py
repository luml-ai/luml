from typing import Any
from pydantic import ValidationError

from service import UvicornService
from _exceptions import HTTPException

app = UvicornService()


@app.get(
    "/healthz",
    summary="Health Check",
    description="Returns the health status of the service",
    tags=["model"],
)
async def healthz():
    return {"status": "healthy"}


@app.get(
    "/manifest",
    summary="Get Model Manifest",
    description="Returns the FNNX model manifest with input/output specifications",
    tags=["model"],
)
async def get_manifest():
    try:
        return app.model_handler.get_manifest()
    except Exception as e:
        return {"error": f"Failed to get manifest: {str(e)}"}


@app.post(
    "/compute",
    summary="Run Model Inference",
    description="Execute inference on the loaded model",
    response_model=dict[str, Any],
    tags=["model"],
)
async def compute(request_data):
    ComputeRequest = app.model_handler.get_request_model()
    try:
        validated_request = ComputeRequest(**request_data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Input validation failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Validation error: {e}")

    try:
        result = await app.model_handler.compute_result(
            validated_request.inputs, validated_request.dynamic_attributes
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model computation failed: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=6005)
