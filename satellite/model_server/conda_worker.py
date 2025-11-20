import json
import logging
import sys
import traceback
from typing import Any

import uvicorn
from openapi_generator import OpenAPIGenerator
from services.base_service import HTTPException
from services.service import UvicornService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [conda_worker] %(message)s"
)
logger = logging.getLogger(__name__)


try:
    logger.info("[INIT] Starting conda_worker...")

    if len(sys.argv) < 2:
        logger.error("[INIT] Missing required extracted_path argument")
        sys.exit(1)

    extracted_path = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    model_data = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}

    import numpy as np
    from fnnx.device import DeviceMap
    from fnnx.handlers.local import LocalHandlerConfig
    from fnnx.runtime import Runtime

    def to_jsonable(obj: Any) -> Any:  # noqa: ANN401
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, dict):
            return {k: to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [to_jsonable(v) for v in obj]
        if isinstance(obj, tuple):
            return [to_jsonable(v) for v in obj]
        return obj

    handler = Runtime(
        bundle_path=extracted_path,
        device_map=DeviceMap(accelerator="cpu", node_device_map={}),
        handler_config=LocalHandlerConfig(auto_cleanup=False),
    )

    async def compute_model(inputs: dict, dynamic_attributes: dict) -> dict:
        try:
            result = await handler.compute_async(inputs, dynamic_attributes)
        except NotImplementedError:
            result = handler.compute(inputs, dynamic_attributes)
        except Exception:
            raise
        return to_jsonable(result)

    openapi_gen = None
    title = None
    description = None

    if model_data:
        model_name = model_data.get("model_name", "").replace("_", " ").upper().split(".")[0]
        title = f"{model_name}"
        description = f"API for {model_data.get('model_name', '')} model"
        openapi_gen = OpenAPIGenerator(
            title=title,
            description=description,
            manifest=model_data.get("manifest"),
            dtypes_schemas=model_data.get("dtypes_schemas"),
            request_schema=model_data.get("request_schema"),
            response_schema=model_data.get("response_schema"),
        )

    app = UvicornService(
        title=title or "Model Conda Compute Service",
        description=description or "Model Conda Compute Service",
        openapi_generator=openapi_gen,
    )

    @app.get("/healthz")
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
            return model_data.get("manifest", {})
        except Exception as error:
            raise HTTPException(
                status_code=500, detail=f"Failed to get manifest: {str(error)}"
            ) from error

    @app.post("/compute")
    async def compute(request_data: dict) -> dict[str, Any]:  # noqa: ANN401
        inputs = request_data.get("inputs")
        if inputs is None:
            raise HTTPException(status_code=400, detail="Missing 'inputs' in request")

        try:
            result = await compute_model(inputs, request_data.get("dynamic_attributes") or {})
            return result
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    if __name__ == "__main__":
        logger.info("[UVICORN] Starting server...")
        uvicorn.run(app, host="0.0.0.0", port=port)

except Exception as e:
    logger.error(f"[ERROR] Fatal error in conda worker: {e}")
    logger.error(f"[ERROR] Traceback: {traceback.format_exc()}")
    sys.exit(1)
