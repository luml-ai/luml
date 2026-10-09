from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from fnnx.utils import to_thread  # type: ignore[import-not-found, import-untyped]
from fnnx.variants.pyfunc import (  # type: ignore[import-not-found, import-untyped]
    PyFunc,
)

if TYPE_CHECKING:
    import pandas as pd


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

        self.input_dtypes = self.fnnx_context.get_value("input_dtypes")
        if not self.input_dtypes and hasattr(self.estimator, "feature_names_in_"):
            with suppress(AttributeError):
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
        x: Any
        if self.input_dtypes:
            x = self._frame(inputs, input_order)
        else:
            x = self.np.column_stack([inputs[col] for col in input_order])
        outputs = {"y": self.estimator.predict(x)}
        if hasattr(self.estimator, "predict_proba"):
            try:
                proba = self.np.asarray(self.estimator.predict_proba(x), dtype=float)
                outputs["y_score"] = proba.max(axis=1) if proba.ndim > 1 else proba
                # the full vector too: per-class drift needs more than the maximum
                outputs["y_proba"] = proba
            except Exception:  # noqa: BLE001 — confidence is best-effort, labels are not
                pass
        return outputs

    def _frame(self, inputs: dict, input_order: list) -> pd.DataFrame:
        """Rebuild the training frame with the dtypes it was fitted on.

        Stacking mixed columns into one array upcasts everything to strings, and a
        ColumnTransformer selecting columns by name cannot work on an array at all.
        """
        import pandas as pd  # type: ignore[import-not-found]

        dtypes: dict[str, type[float] | type[int] | type[object]] = {
            "float": float,
            "int": int,
            "str": object,
        }
        data = {}
        for col in input_order:
            raw = self.np.asarray(inputs[col], dtype=object).ravel()
            series = pd.Series(raw)
            target = dtypes.get(self.input_dtypes.get(col, "str"), object)
            try:
                data[col] = series.astype(target)
            except (TypeError, ValueError):
                data[col] = series
        return pd.DataFrame(data, columns=list(input_order))

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        executor = self.fnnx_context.executor
        return await to_thread(executor, self.compute, inputs, dynamic_attributes)
