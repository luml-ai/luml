from typing import Any, Literal

import numpy as np
import scipy.sparse as sp
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from fnnx.extras.pydantic_models.manifest import (  # type: ignore[import-untyped]
    JSON,
    NDJSON,
)

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore[assignment]


from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)


def resolve_dtype(dtype: Any) -> str:  # noqa: ANN401
    if pd is not None and isinstance(dtype, pd.CategoricalDtype):
        return "str"
    if np.issubdtype(dtype, np.floating):
        return "float"
    if np.issubdtype(dtype, np.integer):
        return "int"
    return "str"

def normalize_inputs(  # noqa: C901
    inputs: Any,  # noqa: ANN401
    input_format: str,
    allow_dmatrix: bool = False,
) -> tuple[object, list[str], dict[str, list[str]]]:
    categorical_features: dict[str, list[str]] = {}

    if pd is not None and isinstance(inputs, pd.DataFrame):
        input_order = list(inputs.columns)
        for col in input_order:
            if isinstance(inputs[col].dtype, pd.CategoricalDtype):
                categorical_features[col] = list(inputs[col].dtype.categories)  # type: ignore[union-attr]
        return inputs, input_order, categorical_features

    if allow_dmatrix:
        try:
            import xgboost as xgb  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "xgboost is required when allow_dmatrix=True to handle DMatrix inputs."
            ) from exc

        if isinstance(inputs, xgb.DMatrix):
            feature_names = inputs.feature_names
            if feature_names is None:
                feature_names = [f"x{i}" for i in range(inputs.num_col())]
            return inputs, list(feature_names), categorical_features


    if sp.issparse(inputs):
        if input_format != "native":
            raise ValueError("Sparse requires input_format='native'")
        if inputs.ndim < 2:  # type: ignore[attr-defined]
            raise ValueError("Input must be at least 2D")
        input_order = [f"x{i}" for i in range(inputs.shape[1])]  # type: ignore[attr-defined]
        return inputs, input_order, categorical_features

    # numpy fallback
    arr = np.asarray(inputs)
    if arr.ndim < 2:
        raise ValueError("Input must be at least 2D")
    input_order = [f"x{i}" for i in range(arr.shape[1])]
    return arr, input_order, categorical_features

def add_unified_inputs(
    builder: PyfuncBuilder,
    inputs: Any,  # noqa: ANN401
    input_order: list[str],
    categorical_features: dict[str, list[str]],
    feature_types: list[str] | None = None,
) -> None:
    for i, name in enumerate(input_order):
        if name in categorical_features:
            dtype = "str"
        elif pd is not None and isinstance(inputs, pd.DataFrame):
            dtype = resolve_dtype(inputs[name].dtype)
        elif feature_types and i < len(feature_types):
            ftype = feature_types[i]
            if ftype in ("float", "f"):
                dtype = "float"
            elif ftype in ("int", "i"):
                dtype = "int"
            else:
                dtype = "str"
        else:
            dtype = "float"

        builder.add_input(
            NDJSON(
                name=name,
                content_type="NDJSON",
                dtype=f"Array[{dtype}]",
                shape=["batch"],
            )
        )

def add_unified_output(
    builder: PyfuncBuilder,
    estimator: Any,  # noqa: ANN401
    x: Any,  # noqa: ANN401
    output_name: str = "y",
) -> None:
    y_pred = estimator.predict(x)
    y_array = np.asarray(y_pred)

    y_shape = ["batch"] + list(y_array.shape[1:])
    y_dtype = resolve_dtype(y_array.dtype)

    builder.add_output(
        NDJSON(
            name=output_name,
            content_type="NDJSON",
            dtype=f"Array[{y_dtype}]",
            shape=y_shape,  # type: ignore
        )
    )

def add_native_io(
    builder: PyfuncBuilder,
    input_schema: Any,  # noqa: ANN401
    output_schema: Any,  # noqa: ANN401
    output_name: str,
) -> None:
    builder.define_dtype("ext::input", input_schema)
    builder.define_dtype("ext::output", output_schema)

    builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::input"))
    builder.add_output(JSON(name=output_name, content_type="JSON", dtype="ext::output"))

def _get_default_deps(
    framework: Literal["xgboost", "lightgbm", "catboost"],
    needs_pandas: bool = False,
) -> list[str]:
    deps = [
        f"{framework}==" + get_version(framework),
        "numpy==" + get_version("numpy"),
        "scipy==" + get_version("scipy"),
    ]

    if framework == "catboost" or needs_pandas:
        deps.append("pandas==" + get_version("pandas"))

    return deps

def add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
    needs_pandas: bool = False,
    framework: Literal["xgboost", "lightgbm", "catboost"] = "xgboost",

) -> None:
    auto_pip_dependencies: list[str] = []
    auto_local_dependencies: list[str] = []

    if dependencies == "all" or extra_code_modules == "auto":
        auto_pip_dependencies, auto_local_dependencies = find_dependencies()

    if dependencies == "all":
        pip_deps = auto_pip_dependencies

    elif dependencies == "default":
        pip_deps = _get_default_deps(framework=framework, needs_pandas=needs_pandas)
        builder.add_fnnx_runtime_dependency()

    else:  # explicit list
        pip_deps = dependencies

    local_dependencies: list[str] = []

    if extra_code_modules == "auto":
        local_dependencies.extend(auto_local_dependencies)

    elif isinstance(extra_code_modules, list):
        local_dependencies.extend(extra_code_modules)

    for dep in pip_deps:
        builder.add_runtime_dependency(dep)

    if extra_dependencies:
        for dep in extra_dependencies:
            builder.add_runtime_dependency(dep)

    local_dependencies = extract_top_level_modules(local_dependencies)

    for module in local_dependencies:
        builder.add_module(module)

def is_sklearn_estimator(obj: object, estimator_cls: type | None) -> bool:
    if estimator_cls is None:
        return False
    return isinstance(obj, estimator_cls)
