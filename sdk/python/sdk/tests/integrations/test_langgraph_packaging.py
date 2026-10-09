from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph
from langgraph.pregel import Pregel

from luml.integrations.langgraph import save_langgraph


class _State(TypedDict):
    value: int


def _increment(state: _State) -> _State:
    return {"value": state["value"] + 1}


def _build_graph() -> Pregel:
    builder = StateGraph(_State)
    builder.add_node("increment", _increment)
    builder.set_entry_point("increment")
    builder.set_finish_point("increment")
    return builder.compile()


def test_manifest_tags(tmp_path: Path) -> None:
    path = str(tmp_path / "graph.luml")
    reference = save_langgraph(
        _build_graph,
        path=path,
        dependencies=["fnnx>=0.0.11"],
        extra_code_modules=None,
    )

    tags = reference.get_manifest()["producer_tags"]
    assert "luml.ai::kind_llm:v1" in tags
    assert not any(
        tag.startswith(("luml.ai::tabular_monitoring:", "luml.ai::llm_monitoring:"))
        for tag in tags
    )
