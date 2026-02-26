import numpy as np
import scipy.sparse
from catboost import CatBoost  # type: ignore[import-untyped]

import pandas as pd

from fnnx.utils import to_thread  # type: ignore[import-untyped]
from fnnx.variants.pyfunc import PyFunc  # type: ignore[import-untyped]


class CatBoostFunc(PyFunc):
    def warmup(self) -> None:
        model_path = self.fnnx_context.get_filepath("model.json")

        if not model_path:
            raise ValueError("model.json not found in fnnx_context")

        self.model = CatBoost()
        self.model.load_model(model_path, format="json")

        self.input_order = self.fnnx_context.get_value("input_order")
        if not self.input_order:
            raise RuntimeError(
                "Input order not found. Make sure to have "
                "'input_order' in the fnnx context."
            )

        self.input_format = self.fnnx_context.get_value("input_format") or "unified"
        self.model_type = self.fnnx_context.get_value("model_type") or "regressor"
        self.categorical_features = (
            self.fnnx_context.get_value("categorical_features") or {}
        )

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:  # noqa: C901
        if self.input_format == "native":
            payload = inputs["payload"]
            pool_input = payload["pool"]
            predict_config = payload.get("predict_config") or {}

            data_format = pool_input.get("data_format", "dense")
            if data_format == "csr":
                x = scipy.sparse.csr_matrix(
                    (
                        np.asarray(pool_input["data"]),
                        np.asarray(pool_input["indices"]),
                        np.asarray(pool_input["indptr"]),
                    ),
                    shape=tuple(pool_input["shape"]),
                )
            elif data_format == "dense":
                x = np.asarray(pool_input["data"])
                if x.ndim == 1:
                    x = x.reshape(1, -1)
            else:
                raise ValueError(
                    f"Unsupported data_format: {data_format!r}. Expected 'dense' or 'csr'."
                )

            predict_kwargs: dict = {}
            if predict_config:
                if predict_config.get("prediction_type") is not None:
                    predict_kwargs["prediction_type"] = predict_config["prediction_type"]
                for key in ["ntree_start", "ntree_end", "thread_count"]:
                    if key in predict_config:
                        predict_kwargs[key] = predict_config[key]

            predictions = self.model.predict(x, **predict_kwargs)
            return {"catboost_output": {"predictions": np.asarray(predictions).tolist()}}

        elif self.categorical_features:
            data: dict = {}
            for col in self.input_order:
                if col in self.categorical_features:
                    categories = self.categorical_features[col]
                    data[col] = pd.Categorical(inputs[col], categories=categories)
                else:
                    data[col] = inputs[col]
            x = pd.DataFrame(data)
        else:
            columns = [inputs[col] for col in self.input_order]
            x = np.column_stack(columns)

        predict_type = "Class" if self.model_type == "classifier" else None
        predict_kwargs = {"prediction_type": predict_type} if predict_type else {}
        predictions = self.model.predict(x, **predict_kwargs)
        return {"y": np.asarray(predictions).tolist()}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)