import json
import logging
import sys
from typing import Any

import uvicorn
from openapi_generator import OpenAPIGenerator
from services.base_service import HTTPException
from services.service import UvicornService

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


try:
    logger.info("Starting...")

    if len(sys.argv) < 2:
        logger.error("Missing required extracted_path argument")
        sys.stderr.flush()
        sys.exit(1)

    extracted_path = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    model_data = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}

    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore[assignment]

    from fnnx.device import DeviceMap
    from fnnx.handlers.local import LocalHandlerConfig
    from fnnx.runtime import Runtime

    def to_jsonable(obj: Any) -> Any:  # noqa: ANN401
        if np is not None:
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
            logger.info("compute_async not implemented, falling back to sync compute")
            result = handler.compute(inputs, dynamic_attributes)
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

    def _extract_upstream_status(error: BaseException) -> tuple[int, str] | None:
        response = getattr(error, "response", None)
        if response is not None:
            status_code = getattr(response, "status_code", None)
            if isinstance(status_code, int) and 400 <= status_code < 600:
                body: str | None = None
                text = getattr(response, "text", None)
                if isinstance(text, str) and text:
                    body = text
                else:
                    try:
                        raw = response.json()  # type: ignore[union-attr]
                        body = json.dumps(raw)
                    except Exception:
                        body = None
                detail = f"{str(error)}: {body}" if body else str(error)
                return status_code, detail

        status_code = getattr(error, "status_code", None)
        if isinstance(status_code, int) and 400 <= status_code < 600:
            return status_code, str(error)

        http_status = getattr(error, "http_status", None)
        if isinstance(http_status, int) and 400 <= http_status < 600:
            return http_status, str(error)

        grpc_code = getattr(error, "code", None)
        if callable(grpc_code):
            grpc_code = grpc_code()
        grpc_to_http = {429: 429, 8: 429, 7: 403, 16: 401, 5: 404, 3: 400, 13: 500, 14: 503}
        if isinstance(grpc_code, int) and grpc_code in grpc_to_http:
            return grpc_to_http[grpc_code], str(error)

        return None

    @app.post("/compute")
    async def compute(request_data: dict) -> dict[str, Any]:  # noqa: ANN401
        inputs = request_data.get("inputs")
        if inputs is None:
            raise HTTPException(status_code=400, detail="Missing 'inputs' in request")

        try:
            return await compute_model(inputs, request_data.get("dynamic_attributes") or {})
        except Exception as error:
            upstream = _extract_upstream_status(error)
            if upstream is not None:
                status_code, detail = upstream
                raise HTTPException(status_code=status_code, detail=detail) from error
            raise HTTPException(
                status_code=500, detail=f"{type(error).__name__}: {error}"
            ) from error

    if __name__ == "__main__":
        logger.info("Starting server...")
        uvicorn.run(app, host="0.0.0.0", port=port)

except Exception:
    logger.exception("Fatal error in conda worker")
    sys.exit(1)
