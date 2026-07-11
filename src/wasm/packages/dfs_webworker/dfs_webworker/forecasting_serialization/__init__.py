"""FNNX serialization for forecasting pipelines.

Mirrors ``prompt_optimization/serialization``: the fitted pipeline is stored as
a JSON spec in ``extra_values`` and rebuilt in the pyfunc's ``warmup`` — no
pickle, no statsmodels results-object serialization. The pipeline module is
bundled via ``add_module`` so it imports inside the runtime, and the produced
bundle carries the forecasting producer tag plus three meta entries
(``forecasting_metrics``, ``registry_metrics``, ``forecasting_chart``).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from importlib import metadata as importlib_metadata

import dfs_webworker.forecasting as forecasting_module
from dfs_webworker.constants import (
    FORECASTING_CHART_TAG,
    FORECASTING_METRICS_TAG,
    FORECASTING_PRODUCER,
    FORECASTING_TAG,
    REGISTRY_METRICS_TAG,
)
from dfs_webworker.forecasting import ForecastingPipeline
from pyfnx_utils.builder import File, PyfuncBuilder, PyFuncSpec
from pyfnx_utils.models import JSON
from pyfnx_utils.models.meta import MetaEntry

_CDIR = os.path.dirname(__file__)
_PYFUNC_SPEC = PyFuncSpec(
    filepath=os.path.join(_CDIR, "_pyfunc.py"), class_name="ForecastingPyFunc"
)
_VERSION = importlib_metadata.version("dfs-webworker")
_RUNTIME_PACKAGES = ("statsmodels", "scipy", "pandas", "numpy")

_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {"forecast": {"type": "array"}},
    "required": ["forecast"],
    "additionalProperties": False,
}


class _JsonSchema:
    """Duck-typed schema: ``define_dtype`` only needs ``model_json_schema``."""

    def __init__(self, schema: dict) -> None:
        self._schema = schema

    def model_json_schema(self) -> dict:
        return self._schema


def _input_schema(has_known_future: bool) -> dict:
    properties: dict[str, dict] = {
        "history": {"type": "array"},
        "horizon": {"type": "integer"},
    }
    if has_known_future:
        properties["future"] = {"type": "array"}
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": properties,
        "required": ["history", "horizon"],
    }


def _chart_without_future(chart: dict) -> dict:
    series = {
        col: {k: v for k, v in payload.items() if k != "future"}
        for col, payload in chart.get("series", {}).items()
    }
    return {"split_date": chart.get("split_date"), "series": series}


def _meta_entry(entry_id: str, tag: str, payload: dict) -> dict:
    return asdict(
        MetaEntry(
            id=entry_id,
            producer=FORECASTING_PRODUCER,
            producer_version=_VERSION,
            producer_tags=[tag],
            payload=payload,
        )
    )


def _write_meta(f: File, metrics: dict, model_config: dict, chart: dict) -> None:
    entries = [
        _meta_entry(
            "forecasting_metrics",
            FORECASTING_METRICS_TAG,
            {"metrics": metrics, "model_config": model_config},
        ),
        _meta_entry("registry_metrics", REGISTRY_METRICS_TAG, {"metrics": metrics}),
        _meta_entry(
            "forecasting_chart", FORECASTING_CHART_TAG, _chart_without_future(chart)
        ),
    ]
    f.create_file("meta.json", json.dumps(entries))


def serialize(
    pipeline: ForecastingPipeline,
    metrics: dict,
    model_config: dict,
    chart: dict,
) -> bytes:
    builder = PyfuncBuilder(
        pyfunc=_PYFUNC_SPEC,
        create_meta_callback=lambda f: _write_meta(f, metrics, model_config, chart),
    )

    builder.define_dtype(
        "ext::in", _JsonSchema(_input_schema(bool(pipeline.known_future_cols)))
    )
    builder.define_dtype("ext::out", _JsonSchema(_OUTPUT_SCHEMA))
    builder.add_input(JSON(name="in", dtype="ext::in"))
    builder.add_output(JSON(name="out", dtype="ext::out"))

    builder.set_extra_values({"pipeline": pipeline.to_dict()})
    builder.set_producer_info(
        name=FORECASTING_PRODUCER, version=_VERSION, tags=[FORECASTING_TAG]
    )

    builder.add_module(forecasting_module.__file__)
    builder.add_fnnx_runtime_dependency(core=True)
    for package in _RUNTIME_PACKAGES:
        builder.add_runtime_dependency(
            f"{package}=={importlib_metadata.version(package)}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "forecasting_model.pyfnx")
        builder.save(path)
        with open(path, "rb") as fh:
            return fh.read()
