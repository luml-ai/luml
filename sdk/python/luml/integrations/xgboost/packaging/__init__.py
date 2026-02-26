import os
import tempfile
from typing import Any, Literal, Union
from warnings import warn

import numpy as np
import xgboost as xgb
from xgboost import Booster

try:
    from xgboost.sklearn import XGBModel
except ImportError:
    XGBModel = None  # type: ignore[assignment, misc]

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]

import scipy.sparse

from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from fnnx.extras.pydantic_models.manifest import (  # type: ignore[import-untyped]
    JSON,
    NDJSON,
)
from pydantic import BaseModel

from luml._constants import FNNX_PRODUCER_NAME
from luml.artifacts.model import ModelReference
from luml.integrations.sklearn.packaging import save_sklearn
from luml.integrations.xgboost.packaging._templates.pyfunc import XGBoostFunc
from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)
from luml.utils.time import get_epoch


class _DMatrixInputSchema(BaseModel):
    data: list[list[float]] | list[float]
    data_format: Literal["dense", "csr"] = "dense"

    # sparse (CSR)
    indices: list[int] | None = None
    indptr: list[int] | None = None
    shape: tuple[int, int] | None = None

    missing: float | None = None
    feature_names: list[str] | None = None
    feature_types: list[str] | None = None


class _XGBoostPredictConfigSchema(BaseModel):
    iteration_range: tuple[int, int] | None = None
    output_margin: bool = False
    pred_leaf: bool = False
    pred_contribs: bool = False
    approx_contribs: bool = False
    pred_interactions: bool = False
    validate_features: bool = True
    training: bool = False
    strict_shape: bool = False


class _XGBoostInputSchema(BaseModel):
    dmatrix: _DMatrixInputSchema
    predict_config: _XGBoostPredictConfigSchema | None = None


class _XGBoostOutputSchema(BaseModel):
    predictions: list[float] | list[list[float]] | list[list[list[float]]]


def _resolve_dtype(dtype: Any) -> str:  # noqa: ANN401
    if pd is not None and isinstance(dtype, pd.CategoricalDtype):
        return "str"
    if np.issubdtype(dtype, np.floating):
        return "float"
    if np.issubdtype(dtype, np.integer):
        return "int"
    return "str"


def _add_io(  # noqa: C901
    builder: PyfuncBuilder,
    estimator: Booster,
    inputs: Any,  # noqa: ANN401
    input_format: Literal["unified", "native"] = "unified",
    categorical_features: dict[str, list[str]] | None = None,
) -> None:
    cat_features: dict[str, list[str]] = categorical_features or {}
    feature_types: list[str] | None = None
    x: object

    if pd is not None and isinstance(inputs, pd.DataFrame):
        input_order = list(inputs.columns)
        for col in input_order:
            col_dtype = inputs[col].dtype
            if isinstance(col_dtype, pd.CategoricalDtype):
                cat_features[col] = list(col_dtype.categories)
        x = inputs

    elif isinstance(inputs, xgb.DMatrix):
        feature_names = inputs.feature_names
        feature_types = list(inputs.feature_types) if inputs.feature_types else None
        num_features = inputs.num_col()

        if feature_names is None:
            feature_names = [f"x{i}" for i in range(num_features)]

        input_order = list(feature_names)
        x = inputs

    elif isinstance(inputs, np.ndarray):
        if inputs.ndim < 2:
            raise ValueError(
                "Input example must be at least 2D for batch dimension inference."
            )
        input_order = [f"x{i}" for i in range(inputs.shape[1])]
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
        raise TypeError(
            f"inputs must be xgb.DMatrix, numpy array, scipy.sparse matrix, "
            f"or pandas DataFrame, got {type(inputs)}"
        )

    extra_values: dict[str, Any] = {
        "input_order": input_order,
        "input_format": input_format,
    }
    if feature_types:
        extra_values["feature_types"] = list(feature_types)
    if cat_features:
        extra_values["categorical_features"] = cat_features

    builder.set_extra_values(extra_values)

    if input_format == "native":
        builder.define_dtype("ext::input", _XGBoostInputSchema)
        builder.define_dtype("ext::output", _XGBoostOutputSchema)
        builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::input"))
        builder.add_output(
            JSON(name="xgboost_output", content_type="JSON", dtype="ext::output")
        )
    else:
        # Unified: separate NDJSON input per feature
        for i, name in enumerate(input_order):
            if name in cat_features:
                dtype = "str"
            elif pd is not None and isinstance(inputs, pd.DataFrame):
                dtype = _resolve_dtype(inputs[name].dtype)
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

        dmatrix_for_pred: xgb.DMatrix
        if isinstance(x, xgb.DMatrix):
            dmatrix_for_pred = x
        else:
            dmatrix_for_pred = xgb.DMatrix(
                x,
                feature_names=input_order,
                enable_categorical=bool(cat_features),
            )

        y_pred = estimator.predict(dmatrix_for_pred)
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


def _get_default_deps(needs_pandas: bool = False) -> list[str]:
    deps = [
        "xgboost==" + get_version("xgboost"),
        "numpy==" + get_version("numpy"),
        "scipy==" + get_version("scipy"),
    ]
    if needs_pandas:
        deps.append("pandas==" + get_version("pandas"))
    return deps


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::xgboost:v1"]


def _add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
    needs_pandas: bool = False,
) -> None:
    auto_pip_dependencies: list[str] = []
    auto_local_dependencies: list[str] = []

    if dependencies == "all" or extra_code_modules == "auto":
        auto_pip_dependencies, auto_local_dependencies = find_dependencies()

    pip_deps: list[str]
    if dependencies == "all":
        pip_deps = auto_pip_dependencies
    elif dependencies == "default":
        pip_deps = _get_default_deps(needs_pandas=needs_pandas)
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


def _is_xgboost_sklearn_estimator(obj: object) -> bool:
    if XGBModel is None:
        return False
    return isinstance(obj, XGBModel)


def save_xgboost(  # noqa: C901
    estimator: "Union[Booster, xgb.XGBModel]",  # noqa: UP007
    inputs: Any,  # noqa: ANN401
    path: str | None = None,
    input_format: Literal["unified", "native"] = "unified",
    categorical_features: dict[str, list[str]] | None = None,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:
    """Save an XGBoost Booster model as a Luml model.

    Args:
        estimator: The XGBoost Booster or XGBModel to save.
        inputs: Example input data for the model.
        path: Path where the model will be saved. Auto-generated if None.
        input_format: Input format for inference:
            - "unified": per-feature NDJSON inputs (default).
            - "native": single JSON payload with DMatrix structure and optional
              predict config; supports both dense row data and CSR sparse matrices.
        categorical_features: Dict mapping feature names to their category values.
        dependencies: Dependency management strategy ("default", "all", or list).
        extra_dependencies: Additional pip dependencies to include.
        extra_code_modules: Local code modules to package ("auto" or list).
        manifest_model_name: Optional name for the model in manifest.
        manifest_model_version: Optional version for the model in manifest.
        manifest_model_description: Optional description for the model.
        manifest_extra_producer_tags: Additional producer tags for model lineage.

    Returns:
        ModelReference: Reference to the saved model."""

    path = path or f"xgboost_model_{get_epoch()}.luml"

    if _is_xgboost_sklearn_estimator(estimator):
        warn(
            "Detected XGBoost scikit-learn estimator. Delegating to save_sklearn().",
            UserWarning,
            stacklevel=2,
        )

        xgboost_dep = f"xgboost=={get_version('xgboost')}"

        if extra_dependencies is None:
            extra_dependencies = [xgboost_dep]

        else:
            extra_dependencies = list(extra_dependencies)
            if not any("xgboost" in dep.lower() for dep in extra_dependencies):
                extra_dependencies.append(xgboost_dep)

        return save_sklearn(
            estimator=estimator,  # type: ignore[arg-type]
            inputs=inputs,
            path=path,
            dependencies=dependencies,
            extra_dependencies=extra_dependencies,
            extra_code_modules=extra_code_modules,
            manifest_model_name=manifest_model_name,
            manifest_model_version=manifest_model_version,
            manifest_model_description=manifest_model_description,
        )

    if not isinstance(estimator, xgb.Booster):
        raise TypeError(
            f"Provided model must be an XGBoost Booster or XGBModel, "
            f"got {type(estimator)}"
        )

    if inputs is None:
        raise ValueError(
            "inputs is required for XGBoost Booster. "
            "Please provide the DMatrix, numpy array, or DataFrame used for training."
        )

    is_dataframe = pd is not None and isinstance(inputs, pd.DataFrame)
    is_ndarray = isinstance(inputs, np.ndarray)
    is_sparse = scipy.sparse.issparse(inputs)
    if (
        not isinstance(inputs, xgb.DMatrix)
        and not is_dataframe
        and not is_ndarray
        and not is_sparse
    ):
        raise TypeError(
            f"inputs must be xgb.DMatrix, numpy array, scipy.sparse matrix, "
            f"or pandas DataFrame, got {type(inputs)}"
        )

    builder = PyfuncBuilder(
        XGBoostFunc,
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
        estimator.save_model(tmp_file.name)
        tmp_model_path = tmp_file.name

    try:
        builder.add_file(tmp_model_path, target_path=model_filename)

        _add_io(
            builder,
            estimator,
            inputs,
            input_format=input_format,
            categorical_features=categorical_features,
        )

        needs_pandas = is_dataframe or bool(categorical_features)

        _add_dependencies(
            builder,
            dependencies,
            extra_dependencies,
            extra_code_modules,
            needs_pandas=needs_pandas,
        )

        builder.save(path)
    finally:
        os.remove(tmp_model_path)

    return ModelReference(path)