import os
import tempfile
from collections.abc import Callable, Sequence
from typing import Any, Literal, cast
from warnings import warn

from fnnx.extras.builder import PyfuncBuilder
from fnnx.extras.pydantic_models.manifest import JSON, Var
from langgraph.pregel import Pregel
from pydantic import BaseModel, create_model

from luml._constants import FNNX_PRODUCER_NAME
from luml.integrations.langgraph.packaging._templates.mermaid import create_mermaid_html
from luml.integrations.langgraph.packaging._templates.pyfunc import LangGraphFunc
from luml.modelref import ModelReference
from luml.utils.deps import find_dependencies, has_dependency
from luml.utils.imports import (
    dyn_import,
    extract_top_level_modules,
    get_object_path,
    get_version,
)
from luml.utils.time import get_epoch


class _CommandSchema(BaseModel):
    resume: Any | None = None
    update: Any | None = None


class _InterruptSchema(BaseModel):
    id: str | None = None
    value: Any | None = None


def _build_schemas(graph: Pregel) -> tuple[type[BaseModel], type[BaseModel]]:
    input_fields = {
        "graph_input": (graph.get_input_schema() | None, None),
        "command": (_CommandSchema | None, None),
        "config": (dict | None, None),
    }

    context_schema = graph.get_context_jsonschema()
    if context_schema is not None:
        input_fields["context"] = (context_schema, ...)  # type: ignore

    input_schema = create_model("InputModel", __base__=BaseModel, **input_fields)  # type: ignore

    output_schema = create_model(
        "OutputModel",
        __base__=BaseModel,
        result=(graph.get_output_schema(), ...),
        interrupts=(Sequence[_InterruptSchema] | None, None),
    )

    return input_schema, output_schema


def _secret(name: str) -> Var:
    return Var(name=name, description="", tags=["dataforce.studio::runtime_secret:v1"])


def _add_dependencies(
    builder: PyfuncBuilder,
    dependencies: Literal["default"] | Literal["all"] | list[str],
    extra_dependencies: list[str] | None,
    extra_code_modules: list[str] | Literal["auto"] | None,
) -> None:
    local_dependencies, pip_dependencies = [], []
    if isinstance(dependencies, str) or extra_code_modules == "auto":
        auto_pip_dependencies, auto_local_dependencies = find_dependencies()

    if isinstance(dependencies, list):
        pip_dependencies = dependencies
    else:
        pip_dependencies = auto_pip_dependencies

    if isinstance(extra_dependencies, list):
        pip_dependencies.extend(extra_dependencies)

    if isinstance(extra_code_modules, list):
        local_dependencies = extra_code_modules
    elif extra_code_modules == "auto":
        local_dependencies = auto_local_dependencies

    local_dependencies = extract_top_level_modules(local_dependencies)
    for dep in pip_dependencies:
        builder.add_runtime_dependency(dep)
    for module in local_dependencies:
        builder.add_module(module)


def _add_io(builder: PyfuncBuilder, graph: Pregel) -> None:
    input_schema, output_schema = _build_schemas(graph)
    builder.define_dtype("ext::input", input_schema)
    builder.define_dtype("ext::output", output_schema)
    builder.add_input(JSON(name="payload", content_type="JSON", dtype="ext::input"))
    builder.add_output(
        JSON(name="graph_output", content_type="JSON", dtype="ext::output")
    )


def _get_default_tags() -> list[str]:
    return [FNNX_PRODUCER_NAME + "::langgraph:v1"]


def save_langgraph(  # noqa: C901
    graph: Pregel | Callable[[], Pregel] | str,
    path: str | None = None,
    dependencies: Literal["default"] | Literal["all"] | list[str] = "default",
    extra_dependencies: list[str] | None = None,
    extra_code_modules: list[str] | Literal["auto"] | None = "auto",
    env_vars: list[str] | None = None,
    manifest_model_name: str | None = None,
    manifest_model_version: str | None = None,
    manifest_model_description: str | None = None,
    manifest_extra_producer_tags: list[str] | None = None,
) -> ModelReference:
    path = path or f"langgraph_model_{get_epoch()}.luml"

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

    graph_creator_callable: Callable[[], Pregel] | None = None
    if isinstance(graph, str):
        graph = cast(Pregel | Callable[[], Pregel], dyn_import(graph))

    if not isinstance(graph, Pregel):
        if not callable(graph):
            raise TypeError(
                "Provided graph is not a Pregel instance or a callable returning one"
            )
        graph_creator_callable = graph
        graph = graph()
        if not isinstance(graph, Pregel):
            raise TypeError("Callable did not return a Pregel instance")

    if graph_creator_callable:
        import cloudpickle

        with tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
        ) as tmp_file:
            cloudpickle.dump(graph_creator_callable, tmp_file)
            callable_path = tmp_file.name
    else:
        _, graph_path = get_object_path(graph)

    builder = PyfuncBuilder(
        LangGraphFunc,
        model_name=manifest_model_name,
        model_description=manifest_model_description,
        model_version=manifest_model_version,
    )

    builder.set_producer_info(
        name=FNNX_PRODUCER_NAME,
        version=get_version("luml"),
        tags=_get_default_tags() + (manifest_extra_producer_tags or []),
    )

    if not graph_creator_callable:
        builder.set_extra_values({"graph_path": graph_path})
    else:
        builder.add_file(callable_path, target_path="graph_creator_callable.pkl")

    _add_io(builder, graph)
    _add_dependencies(builder, dependencies, extra_dependencies, extra_code_modules)

    if env_vars is not None:
        for var_name in env_vars:
            builder.add_env_var(_secret(var_name))

    builder.save(path)

    if graph_creator_callable:
        os.remove(callable_path)

    modelref = ModelReference(path)

    mermaid_code = graph.get_graph(xray=True).draw_mermaid()

    model_card_html = create_mermaid_html(mermaid_code)
    modelref.add_model_card(model_card_html)

    return modelref
