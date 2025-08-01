from promptopt.graph import Graph
from promptopt import __version__ as promptopt_version
from pyfnx_utils.builder import PyfuncBuilder, PyFuncSpec, File
from pyfnx_utils.models.meta import MetaEntry
from pyfnx_utils.models import JSON, Var
import os
import uuid
from dataclasses import asdict
import json

cdir = os.path.dirname(__file__)

spec = PyFuncSpec(
    filepath=os.path.join(cdir, "__fnnx_autogen_content.py"), class_name="GraphPyFunc"
)

PRODUCER = "dataforce.studio/prompt-fusion"


def _add_openai_dynattrs(builder: PyfuncBuilder):
    builder.add_dynamic_attribute(
        Var(
            name="api_key",
            description="API key for the provider",
            tags=[
                f"{PRODUCER}::provider_api_key:v1",
                "dataforce.studio::runtime_secret:v1",
            ],
        )
    )


def _add_ollama_dynattrs(builder: PyfuncBuilder):
    builder.add_dynamic_attribute(
        Var(
            name="base_url",
            description="Base url for the provider",
            tags=[
                f"{PRODUCER}::provider_base_url:v1",
                "dataforce.studio::runtime_secret:v1",
            ],
        )
    )


def _create_meta_callback(f: File, fe_graph_def: dict):
    entry = MetaEntry(
        id="prompt_optimization_fe_graph_def",
        producer=PRODUCER,
        producer_version=promptopt_version,
        producer_tags=[f"{PRODUCER}::graph_fe_def:v1"],
        payload=fe_graph_def,
    )

    f.create_file("meta.json", json.dumps([asdict(entry)]))


def serialize(graph: Graph, provider: str, model: str, fe_graph_def: dict) -> bytes:
    builder = PyfuncBuilder(
        pyfunc=spec,
        create_meta_callback=lambda f: _create_meta_callback(f, fe_graph_def),
    )

    if graph.input_node is None:
        raise ValueError("Graph has no input node")
    if graph.output_node is None:
        raise ValueError("Graph has no output node")

    in_schema = graph.input_node._schema
    out_schema = graph.output_node._schema

    builder.define_dtype("ext::in", in_schema)  # type: ignore
    builder.define_dtype("ext::out", out_schema)  # type: ignore

    builder.add_input(JSON(name="in", dtype="ext::in"))
    builder.add_output(JSON(name="out", dtype="ext::out"))

    builder.set_extra_values(
        {"graph": graph.to_dict(), "model_id": model, "provider": provider}
    )

    if provider == "openai":
        _add_openai_dynattrs(builder)
    elif provider == "ollama":
        _add_ollama_dynattrs(builder)

    builder.set_producer_info(
        name="app.dataforce.studio/prompt-fusion",
        version=promptopt_version,
        tags=["dataforce.studio::prompt_optimization:v1"],
    )
    tmpname = f"dfs-tmp-{uuid.uuid4()}.pyfnx"
    builder.save(tmpname)
    with open(tmpname, "rb") as f:
        content = f.read()
    os.remove(tmpname)
    return content
