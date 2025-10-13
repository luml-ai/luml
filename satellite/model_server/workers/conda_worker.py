import json
import logging
import sys
from typing import Any

import uvicorn
from services.base_service import HTTPException, UvicornBaseService

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [simple_worker] %(message)s"
)
logger = logging.getLogger(__name__)


try:
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
        bundle_path=sys.argv[1],  # extracted_path
        device_map=DeviceMap(accelerator="cpu", node_device_map={}),
        handler_config=LocalHandlerConfig(auto_cleanup=False),
    )

    async def compute_model(inputs: dict, dynamic_attributes: dict) -> dict:
        try:
            result = await handler.compute_async(inputs, dynamic_attributes)
        except NotImplementedError:
            result = handler.compute(inputs, dynamic_attributes)
        return to_jsonable(result)

    app = UvicornBaseService(
        title="Model Conda Compute Service",
        description="Model Conda Compute Service",
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.post("/compute")
    async def compute(request_data: dict) -> dict[str, Any]:  # noqa: ANN401
        inputs = request_data.get("inputs")
        if inputs is None:
            raise HTTPException(status_code=400, detail="Missing 'inputs' in request")

        try:
            return await compute_model(inputs, request_data.get("dynamic_attributes") or {})
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    if __name__ == "__main__":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080

        print(json.dumps({"status": "ready", "port": port}), flush=True)
        uvicorn.run(app, host="127.0.0.1", port=port)

except Exception as error:
    print(json.dumps({"status": "error", "error": str(error)}), flush=True)
    sys.exit(1)
