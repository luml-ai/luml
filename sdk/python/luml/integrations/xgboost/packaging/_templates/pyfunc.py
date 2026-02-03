from typing import Any

import numpy as np
import xgboost as xgb
import scipy.sparse

from fnnx.variants.pyfunc import PyFunc

class XGBoostFunc(PyFunc):
    
    def warmup(self) -> None:
        model_path = self.fnnx_context.get_filepath("model_path")
        
        if not model_path:
            raise ValueError("model_path not found in fnnx_context")
        
        self.model = xgb.Booster()
        self.model.load_model(model_path)
    
    
    def _prepare_dmatrix(self, dmatrix_input: dict) -> xgb.DMatrix:
        data_format = dmatrix_input.get("data_format", "dense")
        data = dmatrix_input["data"]
        missing = dmatrix_input.get("missing")
        feature_names = dmatrix_input.get("feature_names")
        feature_types = dmatrix_input.get("feature_types")
        
        if data_format == "dense":
            data_array = np.asarray(data)
        elif data_format == "csr":
            required_fields = ["indices", "indptr", "shape"]
            missing_fields = [f for f in required_fields if dmatrix_input.get(f) is None]
            if missing_fields:
                raise ValueError(f"CSR format requires: {', '.join(missing_fields)}")
            
            data_array = scipy.sparse.csr_matrix(
                (
                    np.asarray(data),
                    np.asarray(dmatrix_input["indices"]),
                    np.asarray(dmatrix_input["indptr"]),
                ),
                shape=dmatrix_input["shape"],
            )
        else:
            raise ValueError(f"Unknown data_format: {data_format}")
        
        return xgb.DMatrix(
            data_array,
            missing=missing,
            feature_names=feature_names,
            feature_types=feature_types,
        )
    
    def _prepare_inputs(self, payload: dict) -> dict:
        dmatrix_input = payload["dmatrix"]
        predict_config = payload.get("predict_config", {}) or {}
        
        dmatrix = self._prepare_dmatrix(dmatrix_input)
        
        return {
            "dmatrix": dmatrix,
            "predict_config": predict_config,
        }
    
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
        return {"xgboost_output": outputs}
    
    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:

        prepared = self._prepare_inputs(inputs["payload"])
        
        dmatrix = prepared["dmatrix"]
        predict_config = prepared["predict_config"]
        
        predictions = self.model.predict(
            dmatrix,
            iteration_range=predict_config.get("iteration_range"),
            output_margin=predict_config.get("output_margin", False),
            pred_leaf=predict_config.get("pred_leaf", False),
            pred_contribs=predict_config.get("pred_contribs", False),
            approx_contribs=predict_config.get("approx_contribs", False),
            pred_interactions=predict_config.get("pred_interactions", False),
            validate_features=predict_config.get("validate_features", True),
            training=predict_config.get("training", False),
            strict_shape=predict_config.get("strict_shape", False),
        )
        
        outputs = self._prepare_outputs(predictions)
        return self._response(outputs)
    