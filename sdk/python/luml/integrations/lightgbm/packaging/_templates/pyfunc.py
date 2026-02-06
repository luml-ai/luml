from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import scipy.sparse
from fnnx.utils import to_thread
from fnnx.variants.pyfunc import PyFunc


class LightGBMFunc(PyFunc):
    def warmup(self) -> None:
        model_path = self.fnnx_context.get_filepath("model.json")

        if not model_path:
            raise ValueError("model.json not found in fnnx_context")

        self.model = lgb.Booster(model_file=model_path)

    def _prepare_outputs(self, predictions: Any) -> dict:  # noqa: ANN401
        def to_json_serializable(obj: Any) -> Any:  # noqa: ANN401
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, list | tuple):
                return [to_json_serializable(item) for item in obj]
            if isinstance(obj, dict):
                return {key: to_json_serializable(value) for key, value in obj.items()}
            return obj

        return {
            "predictions": to_json_serializable(predictions),
        }

    def _response(self, outputs: dict) -> dict:
        return {"lightgbm_output": outputs}

    def _prepare_inputs(
        self, data_input: dict
    ) -> np.ndarray | pd.DataFrame | scipy.sparse.csr_matrix:
        data_format = data_input.get("data_format", "dense")
        feature_names = data_input.get("feature_names")
        categorical_features = data_input.get("categorical_features") or None

        if data_format == "dense":
            raw_data = data_input["data"]

            if categorical_features:
                df = pd.DataFrame(raw_data, columns=feature_names)

                # Convert categorical_features indices to column names if needed
                cat_columns = []
                for col in categorical_features:
                    if isinstance(col, int):
                        cat_columns.append(df.columns[col])
                    else:
                        cat_columns.append(col)

                for col in cat_columns:
                    df[col] = df[col].astype("category")
                return df

            return np.asarray(raw_data)

        if data_format == "csr":
            return scipy.sparse.csr_matrix(
                (data_input["data"], data_input["indices"], data_input["indptr"]),
                shape=data_input["shape"],
            )

        raise ValueError(f"Unsupported data_format: {data_format}")

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        payload = inputs["payload"]

        data_input = payload["data"]
        predict_config = payload.get("predict_config") or {}

        data = self._prepare_inputs(data_input)

        predictions = self.model.predict(data, **predict_config)

        outputs = self._prepare_outputs(predictions)
        return self._response(outputs)

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
