from fnnx.utils import to_thread  # type: ignore[import-not-found]
from fnnx.variants.pyfunc import PyFunc  # type: ignore[import-not-found]


class SKlearnPyFunc(PyFunc):
    def warmup(self) -> None:
        import numpy as np  # type: ignore[import-not-found]
        from cloudpickle import load  # type: ignore[import-not-found]

        self.np = np
        pickled_estimator_path = self.fnnx_context.get_filepath("estimator.pkl")
        if not pickled_estimator_path:
            raise RuntimeError(
                "Estimator not found. Make sure to save the "
                "estimator as 'estimator.pkl' in the fnnx context."
            )
        with open(pickled_estimator_path, "rb") as f:
            self.estimator = load(f)
        if hasattr(self.estimator, "feature_names_in_"):
            del self.estimator.feature_names_in_

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        if not hasattr(self, "estimator"):
            raise RuntimeError(
                "Estimator is not loaded. Probably warmup() "
                "was not called prior to compute()."
            )
        input_order = self.fnnx_context.get_value("input_order")
        if not input_order:
            raise RuntimeError(
                "Input order not found. Make sure to have "
                "'input_order' in the fnnx context."
            )
        columns = [inputs[col] for col in input_order]
        x = self.np.column_stack(columns)
        return {"y": self.estimator.predict(x)}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
