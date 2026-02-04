from typing import Any

import numpy as np
import lightgbm as lgb
import scipy.sparse

from fnnx.utils import to_thread  # type: ignore[import-not-found]
from fnnx.variants.pyfunc import PyFunc

class LightGBMFunc(PyFunc):

    def warmup(self):
        model_path = self.fnnx_context.get_filepath("model_path")
        
        if not model_path:
            raise ValueError("model_path not found in fnnx_context")
        
        self.model = lgb.Booster(model_file=model_path)


    def _prepare_outputs(self, predictions: Any) -> dict:
        def to_json_serializable(obj: Any) -> Any:
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, (list, tuple)):
                return [to_json_serializable(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: to_json_serializable(value) for key, value in obj.items()}
            return obj
        
        return {
            "predictions": to_json_serializable(predictions),
        }
    
    def _response(self, outputs: dict) -> dict:
        return {"lightgbm_output": outputs}    

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        payload = inputs["payload"]

        data_input = payload["data"]
        predict_config = payload.get("predict_config") or {}

        data_format = data_input.get("data_format", "dense")
        if data_format == "dense":
            data = np.asarray(data_input["data"])
        elif data_format == "csr":
            data = scipy.sparse.csr_matrix(
                (data_input["data"], data_input["indices"], data_input["indptr"]),
                shape=data_input["shape"]
            )
        else:
            raise ValueError(f"Unsupported data_format: {data_format}")

        predictions = self.model.predict(data, **predict_config)
        
        outputs = self._prepare_outputs(predictions)
        return self._response(outputs)
    
    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)

