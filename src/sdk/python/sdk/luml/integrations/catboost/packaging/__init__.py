import os
import tempfile
from typing import Any, Literal, Union

import catboost as ctb  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
from catboost import CatBoost  # type: ignore[import-untyped]
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from pydantic import BaseModel

from luml._constants import FNNX_PRODUCER_NAME
from luml.artifacts.model import ModelReference
from luml.integrations.catboost.packaging._templates.pyfunc import CatBoostFunc
from luml.utils.imports import (
    get_version,
)
from luml.utils.packaging import (
    add_dependencies,
    add_native_io,
    add_unified_inputs,
    add_unified_output,
    normalize_inputs,
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
    x, input_order, categorical_features = normalize_inputs(inputs, input_format)

    model_type = (
        "classifier"
        if estimator.get_all_params().get("loss_function", "")
        in {"Logloss", "CrossEntropy", "MultiClass", "MultiClassOneVsAll"}
        else "regressor"
    )

    builder.set_extra_values(
        {
            "input_order": input_order,
            "input_format": input_format,
            "model_type": model_type,
            **(
                {"categorical_features": categorical_features}
                if categorical_features
                else {}
            ),
        }
    )

    if input_format == "native":
        add_native_io(
            builder,
            _CatBoostInputSchema,
            _CatBoostOutputSchema,
            "catboost_output",
        )
        return

    add_unified_inputs(builder, inputs, input_order, categorical_features)
    add_unified_output(builder, estimator, x)


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::catboost:v1"]


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

        add_dependencies(
            builder,
            dependencies,
            extra_dependencies,
            extra_code_modules,
            framework="catboost",
        )

        builder.save(path)
    finally:
        os.remove(tmp_model_path)

    return ModelReference(path)
