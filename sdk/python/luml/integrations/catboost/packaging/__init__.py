import os
import tempfile
from typing import Any, Literal, Union

import catboost as ctb
from catboost import CatBoost
from fnnx.extras.builder import PyfuncBuilder
from fnnx.extras.pydantic_models.manifest import JSON
from pydantic import BaseModel, create_model

from luml._constants import FNNX_PRODUCER_NAME
from luml.artifacts.model import ModelReference
from luml.integrations.catboost.packaging._templates.pyfunc import CatBoostFunc
from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)
from luml.utils.time import get_epoch


class _DataInputSchema(BaseModel):
    data: list[list[Any]] | list[Any]
    data_format: Literal["dense", "csr"] = "dense"

    # Feature metadata
    feature_names: list[str] | None = None

    # CatBoost-specific feature types
    categorical_features: list[str] | list[int] | None = None
    text_features: list[str] | list[int] | None = None
    embedding_features: list[str] | list[int] | None = None

    # Sparse (CSR)
    indices: list[int] | None = None
    indptr: list[int] | None = None
    shape: tuple[int, int] | None = None


class _PredictConfigSchema(BaseModel):
    prediction_type: Literal[
        "RawFormulaVal", "Class", "Probability", "Exponent", "LogProbability"
    ] = "RawFormulaVal"
    ntree_start: int = 0
    ntree_end: int = 0
    thread_count: int = -1
    verbose: bool | None = None
    task_type: Literal["CPU", "GPU"] = "CPU"


def _build_input_schema() -> type[BaseModel]:
    input_fields = {
        "data": (_DataInputSchema, ...),
        "predict_config": (_PredictConfigSchema | None, None),
    }

    input_schema = create_model(
        "CatBoostInputModel",
        __base__=BaseModel,
        **input_fields,  # type: ignore[call-overload]
    )
    return input_schema


def _build_output_schema() -> type[BaseModel]:
    output_fields = {
        "predictions": (list[float] | list[list[float]] | list[list[list[float]]], ...),
    }

    output_schema = create_model(
        "CatBoostOutputModel",
        __base__=BaseModel,
        **output_fields,  # type: ignore[call-overload]
    )
    return output_schema


def _add_io(builder: PyfuncBuilder) -> None:
    input_schema = _build_input_schema()
    output_schema = _build_output_schema()
    builder.define_dtype("ext::input", input_schema)
    builder.define_dtype("ext::output", output_schema)
    builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::input"))
    builder.add_output(
        JSON(name="catboost_output", content_type="JSON", dtype="ext::output")
    )


def _get_default_deps() -> list[str]:
    return [
        "catboost==" + get_version("catboost"),
        "numpy==" + get_version("numpy"),
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
    path: str | None = None,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:
    path = path or f"catboost_model_{get_epoch()}.luml"

    if not isinstance(estimator, ctb.CatBoost):
        raise TypeError(
            f"Provided model must be a CatBoost model, got {type(estimator)}"
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

    # Determine model type for default prediction_type
    loss_function = estimator.get_all_params().get("loss_function", "")
    classification_losses = [
        "Logloss", "CrossEntropy", "MultiClass", "MultiClassOneVsAll"
    ]
    model_type = "classifier" if loss_function in classification_losses else "regressor"

    builder.add_file(tmp_model_path, target_path=model_filename)
    builder.set_extra_values({
        "input_order": ["payload"],
        "model_path": model_filename,
        "model_type": model_type,
        "loss_function": loss_function,
    })

    _add_io(builder)

    _add_dependencies(
        builder,
        dependencies,
        extra_dependencies,
        extra_code_modules,
    )

    builder.save(path)
    os.remove(tmp_model_path)
    return ModelReference(path)
