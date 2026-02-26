import numpy as np
import xgboost as xgb
from scipy.sparse import csr_matrix

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]

from typing import Union
from fnnx.utils import to_thread  # type: ignore[import-untyped]
from fnnx.variants.pyfunc import PyFunc  # type: ignore[import-untyped]


class XGBoostFunc(PyFunc):
    def warmup(self) -> None:
        model_path = self.fnnx_context.get_filepath("model.json")

        if not model_path:
            raise ValueError("model.json not found in fnnx_context")

        self.model = xgb.Booster()
        self.model.load_model(model_path)

        self.input_order = self.fnnx_context.get_value("input_order")
        if not self.input_order:
            raise RuntimeError(
                "Input order not found. Make sure to have "
                "'input_order' in the fnnx context."
            )

        self.input_format = self.fnnx_context.get_value("input_format") or "unified"
        self.feature_types = self.fnnx_context.get_value("feature_types")
        self.categorical_features = (
            self.fnnx_context.get_value("categorical_features") or {}
        )

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:  # noqa: C901
        x : Union[np.ndarray, pd.DataFrame, csr_matrix]

        if self.input_format == "native":
            payload = inputs["payload"]
            dm_input = payload["dmatrix"]
            predict_config = payload.get("predict_config") or {}

            data_format = dm_input.get("data_format", "dense")
            if data_format == "csr":
                x = csr_matrix(
                    (
                        np.asarray(dm_input["data"]),
                        np.asarray(dm_input["indices"]),
                        np.asarray(dm_input["indptr"]),
                    ),
                    shape=tuple(dm_input["shape"]),
                )
            elif data_format == "dense":
                x = np.asarray(dm_input["data"])
                if x.ndim == 1:
                    x = x.reshape(1, -1)
            else:
                raise ValueError(
                    f"Unsupported data_format: {data_format!r}. "
                    f"Expected 'dense' or 'csr'."
                )

            feature_names = dm_input.get("feature_names") or self.input_order
            dmatrix = xgb.DMatrix(
                x,
                missing=dm_input.get("missing"),
                feature_names=feature_names,
                feature_types=dm_input.get("feature_types") or self.feature_types,
                enable_categorical=bool(self.categorical_features),
            )

            predict_kwargs: dict = {}
            if predict_config:
                iter_range = predict_config.get("iteration_range")
                if iter_range is not None:
                    predict_kwargs["iteration_range"] = tuple(iter_range)
                for key in [
                    "output_margin",
                    "pred_leaf",
                    "pred_contribs",
                    "approx_contribs",
                    "pred_interactions",
                    "validate_features",
                    "training",
                    "strict_shape",
                ]:
                    if key in predict_config:
                        predict_kwargs[key] = predict_config[key]

            predictions = self.model.predict(dmatrix, **predict_kwargs)
            return {"xgboost_output": {"predictions": np.asarray(predictions).tolist()}}

        if self.categorical_features:
            if pd is None:
                raise RuntimeError(
                    "pandas is required for categorical features but is not installed."
                )
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

        dmatrix = xgb.DMatrix(
            x,
            feature_names=self.input_order,
            feature_types=self.feature_types,
            enable_categorical=bool(self.categorical_features),
        )

        predictions = self.model.predict(dmatrix)
        return {"y": np.asarray(predictions).tolist()}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
