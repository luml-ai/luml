import os
import tempfile
from typing import Any, Literal, Union
from warnings import warn

import lightgbm as lgb
import numpy as np
from lightgbm import Booster

try:
    from lightgbm.sklearn import LGBMModel
except ImportError:
    LGBMModel = None  # type: ignore[assignment, misc]

try:
    import pandas as pd
except ImportError:
    pd = None  # type: ignore[assignment]

from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from fnnx.extras.pydantic_models.manifest import (  # type: ignore[import-untyped]
    JSON,
    NDJSON,
)
from pydantic import BaseModel

from luml._constants import FNNX_PRODUCER_NAME
from luml.artifacts.model import ModelReference
from luml.integrations.lightgbm.packaging._templates.pyfunc import LightGBMFunc
from luml.integrations.sklearn.packaging import save_sklearn
from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)
from luml.utils.time import get_epoch


class SparseCsrInput(BaseModel):
    data: list[float]
    indices: list[int]
    indptr: list[int]
    shape: list[int]


def _resolve_dtype(dtype: Any) -> str:  # noqa: ANN401
    if pd is not None and isinstance(dtype, pd.CategoricalDtype):
        return "str"
    if np.issubdtype(dtype, np.floating):
        return "float"
    if np.issubdtype(dtype, np.integer):
        return "int"
    return "str"


def _add_io(
    builder: PyfuncBuilder,
    estimator: Booster,
    inputs: Any,  # noqa: ANN401
    support_sparse: bool = False,
) -> None:
    categorical_features: dict[str, list[str]] = {}

    x: object
    if pd is not None and isinstance(inputs, pd.DataFrame):
        input_order = list(inputs.columns)
        for col in input_order:
            dtype_val = inputs[col].dtype

            if isinstance(dtype_val, pd.CategoricalDtype):
                categorical_features[col] = list(dtype_val.categories)
        x = inputs
    else:
        example = np.asarray(inputs)
        if example.ndim < 2:
            raise ValueError(
                "Input example must be at least 2D for batch dimension inference."
            )
        input_order = [f"x{i}" for i in range(example.shape[1])]
        x = example

    if support_sparse:
        builder.define_dtype("ext::sparse_csr", SparseCsrInput)
        builder.add_input(
            JSON(
                name="sparse_input",
                content_type="JSON",
                dtype="ext::sparse_csr",
            )
        )
    else:
        if pd is not None and isinstance(inputs, pd.DataFrame):
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

    extra_values: dict[str, Any] = {
        "input_order": input_order,
        "support_sparse": support_sparse,
    }
    if categorical_features:
        extra_values["categorical_features"] = categorical_features

    builder.set_extra_values(extra_values)

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


def _get_default_deps(
    needs_pandas: bool = False,
    needs_scipy: bool = False,
) -> list[str]:
    deps = [
        "lightgbm==" + get_version("lightgbm"),
        "numpy==" + get_version("numpy"),
    ]
    if needs_pandas:
        deps.append("pandas==" + get_version("pandas"))
    if needs_scipy:
        deps.append("scipy==" + get_version("scipy"))
    return deps


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::lightgbm:v1"]


def _add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
    needs_pandas: bool = False,
    needs_scipy: bool = False,
) -> None:
    auto_pip_dependencies: list[str] = []
    auto_local_dependencies: list[str] = []

    if dependencies == "all" or extra_code_modules == "auto":
        auto_pip_dependencies, auto_local_dependencies = find_dependencies()

    pip_deps: list[str]
    if dependencies == "all":
        pip_deps = auto_pip_dependencies
    elif dependencies == "default":
        pip_deps = _get_default_deps(needs_pandas=needs_pandas, needs_scipy=needs_scipy)
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
    estimator: "Union[Booster, lgb.LGBMModel]",  # noqa: UP007
    inputs: Any,  # noqa: ANN401
    path: str | None = None,
    support_sparse: bool = False,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:
    """Save a LightGBM model as a Luml model.

    Args:
        estimator: The LightGBM model to save (Booster or LGBMModel).
        inputs: Example input data for the model.
        path: Path where the model will be saved. Auto-generated if None.
        support_sparse: Whether to enable sparse matrix input support.
        dependencies: Dependency management strategy ("default", "all", or list).
        extra_dependencies: Additional pip dependencies to include.
        extra_code_modules: Local code modules to package ("auto" or list).
        manifest_model_name: Optional name for the model in manifest.
        manifest_model_version: Optional version for the model in manifest.
        manifest_model_description: Optional description for the model.
        manifest_extra_producer_tags: Additional producer tags for model lineage.

    Returns:
        ModelReference: Reference to the saved model."""
    path = path or f"lgbm_model_{get_epoch()}.luml"

    if _is_lightgbm_sklearn_estimator(estimator):
        warn(
            "Detected LGBM scikit-learn estimator. Delegating to save_sklearn().",
            UserWarning,
            stacklevel=2,
        )

        lgb_dep = f"lightgbm=={get_version('lightgbm')}"

        if extra_dependencies is None:
            extra_dependencies = [lgb_dep]
        else:
            extra_dependencies = list(extra_dependencies)
            if not any("lightgbm" in dep.lower() for dep in extra_dependencies):
                extra_dependencies.append(lgb_dep)

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
            f"Provided model must be a LightGBM Booster or LGBModel, "
            f"got {type(estimator)}"
        )

    if inputs is None:
        raise ValueError(
            "inputs is required for LightGBM Booster. "
            "Please provide example input data (numpy array or DataFrame)."
        )

    builder = PyfuncBuilder(
        LightGBMFunc,
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

    builder.add_file(tmp_model_path, target_path=model_filename)

    _add_io(builder, estimator, inputs, support_sparse=support_sparse)

    # Determine which optional dependencies are needed
    is_dataframe = pd is not None and isinstance(inputs, pd.DataFrame)
    needs_pandas = is_dataframe
    needs_scipy = support_sparse

    _add_dependencies(
        builder,
        dependencies,
        extra_dependencies,
        extra_code_modules,
        needs_pandas=needs_pandas,
        needs_scipy=needs_scipy,
    )

    builder.save(path)
    os.remove(tmp_model_path)
    return ModelReference(path)
