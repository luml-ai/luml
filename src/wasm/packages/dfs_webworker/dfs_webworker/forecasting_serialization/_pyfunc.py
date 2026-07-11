"""Pyfunc executed by exported forecasting ``.luml`` bundles.

The builder slurps this file's source verbatim into the bundle as
``__pyfunc__.py``; the fnnx runtime then execs it with the bundled
``forecasting`` module on ``sys.path`` (added via ``add_module``). The file is
never imported in the dev tree, so the ``forecasting`` import resolves only at
serve time.
"""

from fnnx.variants.pyfunc import PyFunc  # type: ignore[import-untyped]
from forecasting import ForecastingPipeline  # type: ignore[import-not-found]


class ForecastingPyFunc(PyFunc):
    def warmup(self) -> None:
        spec = self.fnnx_context.get_value("pipeline")
        if not isinstance(spec, dict):
            raise ValueError("Forecasting pipeline spec must be a dictionary")
        self.pipeline = ForecastingPipeline.from_dict(spec)

    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        payload = inputs["in"]
        forecast = self.pipeline.predict(
            payload["history"], payload["horizon"], payload.get("future")
        )
        return {"out": {"forecast": forecast}}

    async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
        return self.compute(inputs, dynamic_attributes)
