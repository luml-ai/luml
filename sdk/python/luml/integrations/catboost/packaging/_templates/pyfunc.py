import numpy as np
import pandas as pd
import scipy.sparse
from catboost import CatBoost  # type: ignore[import-untyped]
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

        # Get categorical features info: {col_name: [categories]}
        self.categorical_features = (
            self.fnnx_context.get_value("categorical_features") or {}
        )
        self.support_sparse = self.fnnx_context.get_value("support_sparse") or False

        # Get model metadata for default prediction_type
        self._model_type = self.fnnx_context.get_value("model_type") or "regressor"
        self._loss_function = self.fnnx_context.get_value("loss_function") or ""

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

        predictions = self.model.predict(x)
        return {"y": predictions.tolist()}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
