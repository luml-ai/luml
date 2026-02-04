import os
import tempfile
from typing import Any, Literal, Union
from warnings import warn

import lightgbm as lgb
from lightgbm import Booster

try:
    from lightgbm.sklearn import LGBMModel
except ImportError:
    LGBMModel = None  # type: ignore[assignment, misc]

from fnnx.extras.builder import PyfuncBuilder
from fnnx.extras.pydantic_models.manifest import JSON
from pydantic import BaseModel, create_model

from luml._constants import FNNX_PRODUCER_NAME
from luml.modelref import ModelReference
from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)
from luml.utils.time import get_epoch

from luml.integrations.lightgbm.packaging._templates.pyfunc import LightGBMFunc
from luml.integrations.sklearn.packaging import save_sklearn


class _DataInputSchema(BaseModel):
    data: list[list[float]] | list[float]
    data_format: Literal["dense", "csr"] = "dense"
    
    # Sparse (CSR)
    indices: list[int] | None = None
    indptr: list[int] | None = None
    shape: tuple[int, int] | None = None


class _PredictConfigSchema(BaseModel):
    start_iteration: int = 0
    num_iteration: int | None = None
    raw_score: bool = False
    pred_leaf: bool = False
    pred_contrib: bool = False
    validate_features: bool = False


def _build_input_schema() -> type[BaseModel]:
    input_fields = {
        "data": (_DataInputSchema, ...),
        "predict_config": (_PredictConfigSchema | None, None),
    }
    
    input_schema = create_model(
        "LightGBMInputModel",
        __base__=BaseModel,
        **input_fields  # type: ignore[arg-type]
    )
    return input_schema


def _build_output_schema() -> type[BaseModel]:
    output_fields = {
        "predictions": (list[float] | list[list[float]] | list[list[list[float]]], ...),
    }
    
    output_schema = create_model(
        "LightGBMOutputModel",
        __base__=BaseModel,
        **output_fields  # type: ignore[arg-type]
    )
    return output_schema


def _add_io(builder: PyfuncBuilder) -> None:
    input_schema = _build_input_schema()
    output_schema = _build_output_schema()
    
    builder.define_dtype("ext::input", input_schema)
    builder.define_dtype("ext::output", output_schema)
    builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::input"))
    builder.add_output(
        JSON(name="lightgbm_output", content_type="JSON", dtype="ext::output")
    )


def _get_default_deps() -> list[str]:
    return [
        "lightgbm==" + get_version("lightgbm"),
        "numpy==" + get_version("numpy"),
        "scipy==" + get_version("scipy"),
    ]

def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::lightgbm:v1"]

def _add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
) -> None:
    auto_pip_dependencies = []
    auto_local_dependencies = []
    
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


def _is_lightgbm_sklearn_estimator(obj: object) -> bool:
    if LGBMModel is None:
        return False
    return isinstance(obj, LGBMModel)

def save_lightgbm(  # noqa: C901
    estimator: "Union[Booster, lgb.LGBMModel]", 
    inputs: Any | None = None, 
    path: str | None = None,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",  
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:

    path = path or f"lgbm_model_{get_epoch()}.luml"

    if _is_lightgbm_sklearn_estimator(estimator):
        warn(
            "Detected LGBM scikit-learn estimator. "
            "Delegating to save_sklearn().",
            UserWarning,
        )

        lgbm_dep = f"lightgbm=={get_version('lightgbm')}"

        if extra_dependencies is None:
            extra_dependencies = [lgbm_dep]
        else:
            extra_dependencies = list(extra_dependencies)
            if not any('lightgbm' in dep.lower() for dep in extra_dependencies):
                extra_dependencies.append(lgbm_dep)

        return save_sklearn(
            estimator=estimator,
            inputs=inputs,
            path=path,
            dependencies=dependencies,
            extra_dependencies=extra_dependencies,
            extra_code_modules=extra_code_modules,
            manifest_model_name=manifest_model_name,
            manifest_model_version=manifest_model_version,
            manifest_model_description=manifest_model_description,
        )    

    if not isinstance(estimator, lgb.Booster):
        raise TypeError(
            f"Provided model must be an LightGBM Booster or LGBModel, got {type(estimator)}"
        )

    builder = PyfuncBuilder(
        LightGBMFunc,
        model_name = manifest_model_name,
        model_description = manifest_model_description,
        model_version = manifest_model_version
    )

    builder.set_producer_info(
        name=FNNX_PRODUCER_NAME,
        version=get_version("luml"),
        tags=_get_default_tags() + (manifest_extra_producer_tags or []),
    )

    model_filename = "model.json" 
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".json") as tmp_file:
        estimator.save_model(tmp_file.name)
        tmp_model_path = tmp_file.name
    
    builder.add_file(tmp_model_path, target_path=model_filename)
    builder.set_extra_values({
        "input_order": ["payload"],
        "model_path": model_filename
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