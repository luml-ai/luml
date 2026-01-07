import os
import tempfile
from typing import TYPE_CHECKING, Any, Literal
from warnings import warn

import numpy as np  # type: ignore[import-not-found]
from fnnx.extras.builder import PyfuncBuilder
from fnnx.extras.pydantic_models.manifest import NDJSON

from luml._constants import FNNX_PRODUCER_NAME
from luml.integrations.sklearn.packaging._template import SKlearnPyFunc
from luml.modelref import ModelReference
from luml.utils.deps import find_dependencies, has_dependency
from luml.utils.imports import get_version
from luml.utils.time import get_epoch

if TYPE_CHECKING:
    from sklearn.base import BaseEstimator

try:
    import pandas as pd  # type: ignore[import-untyped]
except ImportError:
    pd = None  # type: ignore[assignment]


def _resolve_dtype(dtype: np.dtype) -> str:
    if np.issubdtype(dtype, np.floating):
        return "float"
    if np.issubdtype(dtype, np.integer):
        return "int"
    return "str"


def _get_default_deps() -> list[str]:
    return [
        "scikit-learn==" + get_version("sklearn"),
        "scipy==" + get_version("scipy"),
        "numpy==" + get_version("numpy"),
        "cloudpickle==" + get_version("cloudpickle"),
    ]


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::sklearn:v1"]


def _add_io(
    builder: PyfuncBuilder,
    estimator: "BaseEstimator",
    inputs: Any,  # noqa: ANN401
) -> None:
    if pd is not None and isinstance(inputs, pd.DataFrame):
        input_order = list(inputs.columns)
        for col in input_order:
            dtype = _resolve_dtype(inputs[col].dtype)  # type: ignore
            builder.add_input(
                NDJSON(
                    name=col,
                    content_type="NDJSON",
                    dtype=f"Array[{dtype}]",
                    shape=["batch"],
                )
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
                    NDJSON(
                        name=name,
                        content_type="NDJSON",
                        dtype=f"Array[{col_dtype}]",
                        shape=["batch"],
                    )
                )
        else:
            shape = ["batch"] + list(example.shape[1:])
            dtype = _resolve_dtype(example.dtype)
            builder.add_input(
                NDJSON(
                    name="input",
                    content_type="NDJSON",
                    dtype=f"Array[{dtype}]",
                    shape=shape,  # type: ignore
                )
            )
            input_order = ["input"]
        x = example

    builder.set_extra_values({"input_order": input_order})

    y_pred = estimator.predict(x)  # type: ignore
    y_array = np.asarray(y_pred)
    y_shape = ["batch"] + list(y_array.shape[1:])
    y_dtype = _resolve_dtype(y_array.dtype)

    builder.add_output(
        NDJSON(
            name="y",
            content_type="NDJSON",
            dtype=f"Array[{y_dtype}]",
            shape=y_shape,  # type: ignore
        )
    )


def _add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
) -> None:
    if dependencies == "all" or extra_code_modules == "auto":
        auto_pip_dependencies, auto_local_dependencies = find_dependencies()

    if dependencies == "all":
        dependencies = auto_pip_dependencies
    elif dependencies == "default":
        dependencies = _get_default_deps()
        builder.add_fnnx_runtime_dependency()

    local_dependencies = []
    if extra_code_modules == "auto":
        local_dependencies.extend(auto_local_dependencies)
    elif isinstance(extra_code_modules, list):
        local_dependencies.extend(extra_code_modules)

    for dep in dependencies:
        builder.add_runtime_dependency(dep)
    if extra_dependencies:
        for dep in extra_dependencies:
            builder.add_runtime_dependency(dep)
    for module in local_dependencies:
        builder.add_module(module)


def save_sklearn(  # noqa: C901
    estimator: "BaseEstimator",
    inputs: Any,  # noqa: ANN401
    path: str | None = None,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:
    import cloudpickle
    from sklearn.base import BaseEstimator

    if not isinstance(estimator, BaseEstimator):
        raise TypeError(
            f"Expected estimator to be sklearn.BaseEstimator, got {type(estimator)}"
        )

    if isinstance(dependencies, list):
        warn(
            "Overwriting the dependencies might lead to unexpected side-effects, "
            "consider providing `extra_dependencies` instead.",
            stacklevel=2,
        )
        if not has_dependency(dependencies, "fnnx"):
            warn(
                "The provided list of dependencies does not contain `fnnx`",
                stacklevel=2,
            )

    path = path or f"sklearn_model_{get_epoch()}.luml"

    if not callable(getattr(estimator, "predict", None)):
        raise TypeError("Provided estimator must implement a .predict() method")

    builder = PyfuncBuilder(
        pyfunc=SKlearnPyFunc,
        model_name=manifest_model_name,
        model_version=manifest_model_version,
        model_description=manifest_model_description,
    )

    builder.set_producer_info(
        name=FNNX_PRODUCER_NAME,
        version=get_version("luml"),
        tags=_get_default_tags() + (manifest_extra_producer_tags or []),
    )

    _add_io(builder, estimator, inputs)
    _add_dependencies(builder, dependencies, extra_dependencies, extra_code_modules)

    with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
        cloudpickle.dump(estimator, tmp)
        estimator_path = tmp.name
    builder.add_file(estimator_path, "estimator.pkl")

    builder.save(path)

    os.remove(estimator_path)
    return ModelReference(path)
