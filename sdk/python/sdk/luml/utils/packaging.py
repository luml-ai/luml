import io
import json
import os
import stat
import tarfile
import tempfile
from collections.abc import Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import scipy.sparse as sp
from fnnx.extras.builder import PyfuncBuilder  # type: ignore[import-untyped]
from fnnx.extras.pydantic_models.manifest import (  # type: ignore[import-untyped]
    JSON,
    NDJSON,
)

from luml._constants import FNNX_PRODUCER_NAME

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore[assignment]


from luml.utils.deps import find_dependencies
from luml.utils.imports import (
    extract_top_level_modules,
    get_version,
)

if TYPE_CHECKING:
    from luml.utils.reference_profile import TaskType

TABULAR_MONITORING_TAG = FNNX_PRODUCER_NAME + "::tabular_monitoring:v1"
REFERENCE_PROFILE_FILENAME = "reference_profile.json"


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


def add_reference_profile(
    artifact_path: str,
    reference_data: Any,  # noqa: ANN401
    task_type: "TaskType",
    predict: Callable[[Any], Any],
    *,
    predict_proba: Callable[[Any], Any] | None = None,
    output_names: list[str] | None = None,
    class_names: list[str] | None = None,
    horizons: list[str] | None = None,
    additional_producer_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Compute the monitoring reference profile and embed it in a saved artifact.

    Runs the canonical, dependency-light profile computation over ``reference_data``
    (the training features) and writes the plain-JSON result into the artifact as
    ``reference_profile.json``. Call it *after* ``builder.save(path)``: the profile has
    to sit at the root of the archive, next to ``manifest.json``, because that is where
    the model server reads it from — the builder's file API would nest it under
    ``variant_artifacts/extra_files/``, where the profile is never found. Producer tags
    supplied through ``additional_producer_tags`` are stamped in the same rewrite.

    The pandas-dependent canonical module is imported lazily so importing this module
    (and packaging without ``reference_data``) stays pandas-optional.
    """
    from luml.utils.reference_profile import build_reference_profile

    profile = build_reference_profile(
        reference_data,
        task_type,
        predict,
        predict_proba=predict_proba,
        output_names=output_names,
        class_names=class_names,
        horizons=horizons,
    )
    embed_reference_profile(
        artifact_path,
        profile,
        additional_producer_tags=additional_producer_tags,
    )
    return profile


def embed_reference_profile(
    artifact_path: str,
    profile: dict[str, Any],
    *,
    additional_producer_tags: list[str] | None = None,
) -> None:
    """Write ``reference_profile.json`` into the root of an fnnx tar artifact.

    Every existing member (manifest, estimator, variant artifacts, …) is copied through
    unchanged and any previous profile member is replaced, so the call is idempotent.
    Requested producer tags are added to the bundled manifest in the same atomic
    rewrite.
    """
    payload = json.dumps(profile).encode("utf-8")

    with open(artifact_path, "rb") as handle:
        source = io.BytesIO(handle.read())

    output = io.BytesIO()
    with (
        tarfile.open(fileobj=source, mode="r:*") as src,
        tarfile.open(fileobj=output, mode="w") as dst,
    ):
        manifest_found = False
        for member in src.getmembers():
            if member.name == REFERENCE_PROFILE_FILENAME:
                continue
            content = src.extractfile(member) if member.isreg() else None
            if member.name == "manifest.json":
                manifest_found = True
                if additional_producer_tags:
                    if content is None:
                        raise ValueError("Artifact manifest cannot be read")
                    manifest = json.loads(content.read())
                    producer_tags = manifest.get("producer_tags")
                    if not isinstance(producer_tags, list) or not all(
                        isinstance(tag, str) for tag in producer_tags
                    ):
                        raise ValueError("Artifact manifest has invalid producer_tags")
                    manifest["producer_tags"] = list(
                        dict.fromkeys(producer_tags + additional_producer_tags)
                    )
                    manifest_payload = json.dumps(manifest).encode("utf-8")
                    member.size = len(manifest_payload)
                    content = io.BytesIO(manifest_payload)
            dst.addfile(member, content)

        if additional_producer_tags and not manifest_found:
            raise ValueError("Artifact manifest is missing")

        info = tarfile.TarInfo(name=REFERENCE_PROFILE_FILENAME)
        info.size = len(payload)
        info.mode = 0o644
        dst.addfile(info, io.BytesIO(payload))

    artifact_mode = stat.S_IMODE(os.stat(artifact_path).st_mode)
    artifact_dir = os.path.dirname(os.path.abspath(artifact_path))
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=artifact_dir,
            prefix=".luml-profile-",
            delete=False,
        ) as handle:
            temporary_path = handle.name
            handle.write(output.getvalue())
        os.chmod(temporary_path, artifact_mode)
        os.replace(temporary_path, artifact_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            with suppress(FileNotFoundError):
                os.unlink(temporary_path)
