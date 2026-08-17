from fnnx.utils import to_thread  # type: ignore[import-not-found, import-untyped]
from fnnx.variants.pyfunc import (  # type: ignore[import-not-found, import-untyped]
    PyFunc,
)


class SKlearnPyFunc(PyFunc):
    def warmup(self) -> None:
        import numpy as np  # type: ignore[import-not-found]
        from cloudpickle import load  # type: ignore[import-not-found, import-untyped]

        self.np = np
        pickled_estimator_path = self.fnnx_context.get_filepath("estimator.pkl")
        if not pickled_estimator_path:
            raise RuntimeError(
                "Estimator not found. Make sure to save the "
                "estimator as 'estimator.pkl' in the fnnx context."
            )
        with open(pickled_estimator_path, "rb") as f:
            self.estimator = load(f)

        # An estimator fitted on a DataFrame gets one back (see compute), so its recorded
        # column names still match. Only the positional path needs them gone: there the
        # inputs arrive as one array and the names would trip sklearn's column check. On a
        # Pipeline the attribute is a read-only property forwarded from the first step and
        # cannot be dropped — sklearn then merely warns, which is harmless here.
        self.input_dtypes = self.fnnx_context.get_value("input_dtypes")
        if not self.input_dtypes and hasattr(self.estimator, "feature_names_in_"):
            try:
                del self.estimator.feature_names_in_
            except AttributeError:
                pass

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
        if self.input_dtypes:
            x = self._frame(inputs, input_order)
        else:
            x = self.np.column_stack([inputs[col] for col in input_order])
        return {"y": self.estimator.predict(x)}

    def _frame(self, inputs: dict, input_order: list):
        """Rebuild the training frame: named columns, each with the dtype it was fitted on.

        Stacking mixed columns into one array upcasts everything to strings, and a
        ColumnTransformer selecting columns by name cannot work on an array at all.
        """
        import pandas as pd  # type: ignore[import-not-found]

        dtypes = {"float": "float64", "int": "int64", "str": "object"}
        data = {}
        for col in input_order:
            series = pd.Series(inputs[col])
            target = dtypes.get(self.input_dtypes.get(col, "str"), "object")
            try:
                data[col] = series.astype(target)
            except (TypeError, ValueError):
                # a column that cannot be cast (nulls in an int column, say) is passed on
                # as it arrived — sklearn will raise with a message about that column
                data[col] = series
        return pd.DataFrame(data, columns=list(input_order))

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
