import numpy as np
import pandas as pd
import scipy.sparse
import xgboost as xgb
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

        self.feature_types = self.fnnx_context.get_value("feature_types")
        self.support_sparse = self.fnnx_context.get_value("support_sparse") or False
        self.categorical_features = (
            self.fnnx_context.get_value("categorical_features") or {}
        )

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:  # noqa: C901
        x: object
        if self.support_sparse:
            sparse_input = inputs["sparse_input"]
            sparse_data = np.asarray(sparse_input["data"])
            indices = np.asarray(sparse_input["indices"])
            indptr = np.asarray(sparse_input["indptr"])
            shape = tuple(sparse_input["shape"])

            x = scipy.sparse.csr_matrix((sparse_data, indices, indptr), shape=shape)
        elif self.categorical_features:
            data: dict[str, object] = {}
            for col in self.input_order:
                if col in self.categorical_features:
                    categories = self.categorical_features[col]
                    data[col] = pd.Categorical(
                        inputs[col], categories=categories
                    )
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
        return {"y": predictions.tolist()}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
