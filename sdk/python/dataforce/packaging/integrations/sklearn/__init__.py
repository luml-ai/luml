from typing import Any

try:
    from sklearn.base import BaseEstimator  # type: ignore[import-not-found]
except ImportError:
    BaseEstimator = None

try:
    import cloudpickle  # type: ignore[import-not-found]
except ImportError:
    cloudpickle = None

try:
    import pandas as pd  # type: ignore[import-untyped]
except ImportError:
    pd = None


import os
import shutil
import tempfile

import numpy as np  # type: ignore[import-not-found]
from pyfnx_utils.builder import PyfuncBuilder  # type: ignore[import-untyped]
from pyfnx_utils.models.manifest import NDJSON  # type: ignore[import-untyped]

from dataforce.packaging.integrations.sklearn.template import SKlearnPyFunc
from dataforce.packaging.utils import get_version


def _resolve_dtype(dtype: np.dtype) -> str:
    if np.issubdtype(dtype, np.floating):
        return "float"
    if np.issubdtype(dtype, np.integer):
        return "int"
    return "str"


def save(
    estimator: Any,  # noqa: ANN401
    inputs: Any,  # noqa: ANN401
    path: str = "model.dfs",
    model_name: str | None = None,
    model_version: str | None = None,
    model_description: str | None = None,
) -> None:
    if not cloudpickle:
        raise RuntimeError("cloudpickle is not installed")
    if not BaseEstimator:
        raise RuntimeError("sklearn is not installed")

    if not callable(getattr(estimator, "predict", None)):
        raise TypeError("Provided estimator must implement a .predict() method")

    builder = PyfuncBuilder(
        pyfunc=SKlearnPyFunc,
        model_name=model_name,
        model_version=model_version,
        model_description=model_description,
    )

    if pd is not None and isinstance(inputs, pd.DataFrame):
        input_order = list(inputs.columns)
        for col in input_order:
            dtype = _resolve_dtype(inputs[col].dtype)
            builder.add_input(
                NDJSON(name=col, dtype=f"Array[{dtype}]", shape=["batch"])
            )
        x = inputs
    else:
        example = np.asarray(inputs)
        if example.ndim < 2:
            raise ValueError(
                "Input example must be at least 2D for batch dimension inference."
            )
        if example.ndim == 2:
            input_order = [f"x{i}" for i in range(example.shape[1])]
            for i, name in enumerate(input_order):
                col_dtype = _resolve_dtype(example[:, i].dtype)
                builder.add_input(
                    NDJSON(name=name, dtype=f"Array[{col_dtype}]", shape=["batch"])
                )
        else:
            shape = ["batch"] + list(example.shape[1:])
            dtype = _resolve_dtype(example.dtype)
            builder.add_input(
                NDJSON(name="input", dtype=f"Array[{dtype}]", shape=shape)
            )
            input_order = ["input"]
        x = example

    builder.set_extra_values({"input_order": input_order})

    y_pred = estimator.predict(x)
    y_array = np.asarray(y_pred)
    y_shape = ["batch"] + list(y_array.shape[1:])
    y_dtype = _resolve_dtype(y_array.dtype)

    builder.add_output(NDJSON(name="y", dtype=f"Array[{y_dtype}]", shape=y_shape))

    dependencies = [
        "scikit-learn==" + get_version("sklearn"),
        "scipy==" + get_version("scipy"),
        "numpy==" + get_version("numpy"),
        "cloudpickle==" + get_version("cloudpickle"),
    ]
    for dep in dependencies:
        builder.add_runtime_dependency(dep)
    builder.add_fnnx_runtime_dependency()

    with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
        cloudpickle.dump(estimator, tmp)
        estimator_path = tmp.name
    builder.add_file(estimator_path, "estimator.pkl")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_model_path = os.path.join(tmpdir, "model.pyfnx")
        builder.save(tmp_model_path)
        shutil.move(tmp_model_path, path)

    os.remove(estimator_path)
