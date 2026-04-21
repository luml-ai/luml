import os
import tempfile
from typing import Any, Literal, Union
from warnings import warn

import numpy as np
import pandas as pd
import scipy.sparse as sp
import xgboost as xgb
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from pydantic import BaseModel
from xgboost import Booster
from xgboost.sklearn import XGBModel

from luml._constants import FNNX_PRODUCER_NAME
from luml.artifacts.model import ModelReference
from luml.integrations.sklearn.packaging import save_sklearn
from luml.integrations.xgboost.packaging._templates.pyfunc import XGBoostFunc
from luml.utils.imports import (
    get_version,
)
from luml.utils.packaging import (
    add_dependencies,
    add_native_io,
    add_unified_inputs,
    add_unified_output,
    is_sklearn_estimator,
    normalize_inputs,
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


def _add_io(
    builder: PyfuncBuilder,
    estimator: xgb.Booster,
    inputs: Any,  # noqa: ANN401
    input_format: Literal["unified", "native"] = "unified",
) -> None:
    x, input_order, categorical_features = normalize_inputs(
        inputs, input_format, allow_dmatrix=True
    )

    feature_types = (
        list(inputs.feature_types)
        if isinstance(inputs, xgb.DMatrix) and inputs.feature_types
        else None
    )

    builder.set_extra_values(
        {
            "input_order": input_order,
            "input_format": input_format,
            "categorical_features": categorical_features,
            **({"feature_types": feature_types} if feature_types else {}),
        }
    )

    if input_format == "native":
        add_native_io(
            builder,
            _XGBoostInputSchema,
            _XGBoostOutputSchema,
            "xgboost_output",
        )
        return

    add_unified_inputs(
        builder, inputs, input_order, categorical_features, feature_types
    )

    if not isinstance(x, xgb.DMatrix):
        x = xgb.DMatrix(
            x,
            feature_names=input_order,
            enable_categorical=bool(categorical_features),
        )

    add_unified_output(builder, estimator, x)


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::xgboost:v1"]


def save_xgboost(  # noqa: C901
    estimator: "Union[Booster, xgb.XGBModel]",  # noqa: UP007
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
    """Save an XGBoost Booster model as a Luml model.

    Args:
        estimator: The XGBoost Booster or XGBModel to save.
        inputs: Example input data for the model.
        path: Path where the model will be saved. Auto-generated if None.
        input_format: Input format for inference:
            - "unified": per-feature NDJSON inputs (default).
            - "native": single JSON payload with DMatrix structure and optional
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

    path = path or f"xgboost_model_{get_epoch()}.luml"

    if is_sklearn_estimator(estimator, XGBModel):
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

    is_dataframe = isinstance(inputs, pd.DataFrame)
    is_ndarray = isinstance(inputs, np.ndarray)
    is_sparse = sp.issparse(inputs)
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
        )

        needs_pandas = isinstance(inputs, pd.DataFrame)

        add_dependencies(
            builder,
            dependencies,
            extra_dependencies,
            extra_code_modules,
            needs_pandas=needs_pandas,
            framework="xgboost",
        )

        builder.save(path)
    finally:
        os.remove(tmp_model_path)

    return ModelReference(path)
