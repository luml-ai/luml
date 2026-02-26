import os
import tempfile
from typing import Any, Literal, Union

import catboost as ctb  # type: ignore[import-untyped]
import numpy as np
from catboost import CatBoost  # type: ignore[import-untyped]
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from fnnx.extras.pydantic_models.manifest import (  # type: ignore[import-untyped]
    JSON,
    NDJSON,
)
from pydantic import BaseModel

import pandas as pd

import scipy

from luml._constants import FNNX_PRODUCER_NAME
from luml.artifacts.model import ModelReference
from luml.integrations.catboost.packaging._templates.pyfunc import CatBoostFunc
from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)
from luml.utils.time import get_epoch


class _CatBoostDataInputSchema(BaseModel):
    data: list[list[float]] | list[float]
    data_format: Literal["dense", "csr"] = "dense"

    # sparse (CSR)
    indices: list[int] | None = None
    indptr: list[int] | None = None
    shape: tuple[int, int] | None = None


class _CatBoostPredictConfigSchema(BaseModel):
    prediction_type: str | None = None  # "Probability", "Class", "RawFormulaVal", etc.
    ntree_start: int = 0
    ntree_end: int = 0
    thread_count: int = -1


class _CatBoostInputSchema(BaseModel):
    pool: _CatBoostDataInputSchema
    predict_config: _CatBoostPredictConfigSchema | None = None


class _CatBoostOutputSchema(BaseModel):
    predictions: list[float] | list[list[float]]


def _resolve_dtype(dtype: Any) -> str:  # noqa: ANN401
    if isinstance(dtype, pd.CategoricalDtype):
        return "str"
    if np.issubdtype(dtype, np.floating):
        return "float"
    if np.issubdtype(dtype, np.integer):
        return "int"
    return "str"


def _add_io(
    builder: PyfuncBuilder,
    estimator: CatBoost,
    inputs: Any,  # noqa: ANN401
    input_format: Literal["unified", "native"] = "unified",
) -> None:
    categorical_features: dict[str, list[str]] = {}

    x: object
    if isinstance(inputs, pd.DataFrame):
        input_order = list(inputs.columns)
        for col in input_order:
            dtype_val = inputs[col].dtype

            if isinstance(dtype_val, pd.CategoricalDtype):
                categorical_features[col] = list(dtype_val.categories)
        x = inputs
    elif scipy.sparse.issparse(inputs):
        if input_format != "native":
            raise ValueError(
                "Sparse matrix inputs require input_format='native'. "
                "Unified format cannot split a sparse matrix into per-feature columns."
            )
        if inputs.ndim < 2:
            raise ValueError(
                "Input example must be at least 2D for batch dimension inference."
            )
        input_order = [f"x{i}" for i in range(inputs.shape[1])]
        x = inputs
    else:
        example = np.asarray(inputs)
        if example.ndim < 2:
            raise ValueError(
                "Input example must be at least 2D for batch dimension inference."
            )
        input_order = [f"x{i}" for i in range(example.shape[1])]
        x = example

    _classification_losses = {"Logloss", "CrossEntropy", "MultiClass", "MultiClassOneVsAll"}
    model_type = (
        "classifier"
        if estimator.get_all_params().get("loss_function", "") in _classification_losses
        else "regressor"
    )

    extra_values: dict[str, Any] = {
        "input_order": input_order,
        "input_format": input_format,
        "model_type": model_type,
    }
    if categorical_features:
        extra_values["categorical_features"] = categorical_features

    builder.set_extra_values(extra_values)

    if input_format == "native":
        builder.define_dtype("ext::input", _CatBoostInputSchema)
        builder.define_dtype("ext::output", _CatBoostOutputSchema)
        builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::input"))
        builder.add_output(
            JSON(name="catboost_output", content_type="JSON", dtype="ext::output")
        )
    else:
        if isinstance(inputs, pd.DataFrame):
            for col in input_order:
                dtype = _resolve_dtype(inputs[col].dtype)
                builder.add_input(
                    NDJSON(
                        name=col,
                        content_type="NDJSON",
                        dtype=f"Array[{dtype}]",
                        shape=["batch"],
                    )
                )
        else:
            # inputs is a dense numpy array here (sparse is rejected for unified above)
            for i, name in enumerate(input_order):
                col_dtype_str = _resolve_dtype(np.asarray(inputs)[:, i].dtype)
                builder.add_input(
                    NDJSON(
                        name=name,
                        content_type="NDJSON",
                        dtype=f"Array[{col_dtype_str}]",
                        shape=["batch"],
                    )
                )

        y_pred = estimator.predict(x)
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


def _get_default_deps() -> list[str]:
    return [
        "catboost==" + get_version("catboost"),
        "numpy==" + get_version("numpy"),
        "pandas==" + get_version("pandas"),
        "scipy==" + get_version("scipy"),
    ]


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::catboost:v1"]


def _add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
) -> None:
    auto_pip_dependencies: list[str] = []
    auto_local_dependencies: list[str] = []

    if dependencies == "all" or extra_code_modules == "auto":
        auto_pip_dependencies, auto_local_dependencies = find_dependencies()

    pip_deps: list[str]
    if dependencies == "all":
        pip_deps = auto_pip_dependencies
    elif dependencies == "default":
        pip_deps = _get_default_deps()
        builder.add_fnnx_runtime_dependency()
    else:
        pip_deps = dependencies

    local_dependencies = []
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


def save_catboost(
    estimator: "Union[CatBoost, ctb.CatBoostClassifier, ctb.CatBoostRegressor]",  # noqa: UP007
    inputs: Any,  # noqa: ANN401
    path: str | None = None,
    input_format: Literal["unified", "native"] = "unified",
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:
    """Save a CatBoost model as a Luml model.

    Args:
        estimator: The CatBoost model to save (CatBoost, CatBoostClassifier,
            or CatBoostRegressor).
        inputs: Example input data for the model.
        path: Path where the model will be saved. Auto-generated if None.
        input_format: Input format for inference:
            - "unified": per-feature NDJSON inputs (default).
            - "native": single JSON payload with pool structure and optional
              predict config; supports both dense row data and CSR sparse matrices.
        dependencies: Dependency management strategy ("default", "all", or list).
        extra_dependencies: Additional pip dependencies to include.
        extra_code_modules: Local code modules to package ("auto" or list).
        manifest_model_name: Optional name for the model in manifest.
        manifest_model_version: Optional version for the model in manifest.
        manifest_model_description: Optional description for the model.
        manifest_extra_producer_tags: Additional producer tags for model lineage.

    Returns:
        ModelReference: Reference to the saved model."""
    path = path or f"catboost_model_{get_epoch()}.luml"

    if not isinstance(estimator, ctb.CatBoost):
        raise TypeError(
            f"Provided model must be a CatBoost model, got {type(estimator)}"
        )

    if inputs is None:
        raise ValueError(
            "inputs is required for CatBoost. "
            "Please provide example input data (numpy array or DataFrame)."
        )

    builder = PyfuncBuilder(
        CatBoostFunc,
        model_name=manifest_model_name,
        model_description=manifest_model_description,
        model_version=manifest_model_version,
    )

    builder.set_producer_info(
        name=FNNX_PRODUCER_NAME,
        version=get_version("luml"),
        tags=_get_default_tags() + (manifest_extra_producer_tags or []),
    )

    model_filename = "model.json"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_file:
        estimator.save_model(tmp_file.name, format="json")
        tmp_model_path = tmp_file.name

    try:
        builder.add_file(tmp_model_path, target_path=model_filename)

        _add_io(builder, estimator, inputs, input_format=input_format)

        _add_dependencies(
            builder,
            dependencies,
            extra_dependencies,
            extra_code_modules,
        )

        builder.save(path)
    finally:
        os.remove(tmp_model_path)

    return ModelReference(path)