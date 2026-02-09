from typing import Any

import numpy as np
import scipy.sparse
from catboost import CatBoost, Pool
from fnnx.utils import to_thread
from fnnx.variants.pyfunc import PyFunc


class CatBoostFunc(PyFunc):
    def warmup(self) -> None:
        model_path = self.fnnx_context.get_filepath("model.json")

        if not model_path:
            raise ValueError("model.json not found in fnnx_context")

        self.model = CatBoost()
        self.model.load_model(model_path, format="json")

        # Get model metadata for default prediction_type
        self._model_type = self.fnnx_context.get_value("model_type") or "regressor"
        self._loss_function = self.fnnx_context.get_value("loss_function") or ""

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
        return {"catboost_output": outputs}

    def _prepare_inputs(
        self, data_input: dict
    ) -> Pool | np.ndarray | scipy.sparse.csr_matrix:
        data_format = data_input.get("data_format", "dense")
        feature_names = data_input.get("feature_names")

        # CatBoost-specific feature types
        cat_features = data_input.get("categorical_features") or None
        text_features = data_input.get("text_features") or None
        embedding_features = data_input.get("embedding_features") or None

        has_special_features = cat_features or text_features or embedding_features

        if data_format == "dense":
            raw_data = data_input["data"]

            if has_special_features:
                return Pool(
                    data=raw_data,
                    feature_names=feature_names,
                    cat_features=cat_features,
                    text_features=text_features,
                    embedding_features=embedding_features,
                )

            return np.asarray(raw_data)

        if data_format == "csr":
            required_fields = ["data", "indices", "indptr", "shape"]
            missing_fields = [f for f in required_fields if data_input.get(f) is None]
            if missing_fields:
                raise ValueError(f"CSR format requires: {', '.join(missing_fields)}")

            sparse_data = scipy.sparse.csr_matrix(
                (data_input["data"], data_input["indices"], data_input["indptr"]),
                shape=data_input["shape"],
            )

            if has_special_features:
                return Pool(
                    data=sparse_data,
                    feature_names=feature_names,
                    cat_features=cat_features,
                    text_features=text_features,
                    embedding_features=embedding_features,
                )

            return sparse_data

        raise ValueError(f"Unsupported data_format: {data_format}")

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        payload = inputs["payload"]

        data_input = payload["data"]
        predict_config = payload.get("predict_config") or {}

        data = self._prepare_inputs(data_input)

        # Default prediction_type based on model type and loss function
        if self._model_type == "classifier":
            default_prediction_type = "Class"
        elif self._loss_function in ["Poisson", "Tweedie"]:
            default_prediction_type = "Exponent"
        else:
            default_prediction_type = "RawFormulaVal"

        prediction_type = predict_config.get("prediction_type", default_prediction_type)
        predictions = self.model.predict(
            data,
            prediction_type=prediction_type,
            ntree_start=predict_config.get("ntree_start", 0),
            ntree_end=predict_config.get("ntree_end", 0),
            thread_count=predict_config.get("thread_count", -1),
            verbose=predict_config.get("verbose"),
            task_type=predict_config.get("task_type", "CPU"),
        )

        outputs = self._prepare_outputs(predictions)
        return self._response(outputs)

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
