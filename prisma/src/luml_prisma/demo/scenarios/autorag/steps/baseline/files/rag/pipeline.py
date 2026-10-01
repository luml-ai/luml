"""LangGraph RAG pipeline: retrieve -> generate.

Nodes stay tracker-free so the compiled graph can be packaged with
save_langgraph; per-node timing is recorded into the state and turned into
trace spans by the eval harness.
"""

import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from rag.text import tokenize

TOP_K = 5


class RAGState(TypedDict, total=False):
    question: str
    candidates: list[dict[str, Any]]
    answer: str
    spans: list[dict[str, Any]]


def _best_sentence(question: str, chunk: str) -> str:
    q_tokens = set(tokenize(question))
    sentences = [s.strip() for s in chunk.replace("\n", " ").split(". ") if s.strip()]
    if not sentences:
        return chunk
    return max(sentences, key=lambda s: len(q_tokens & set(tokenize(s))))


def build_graph(retriever):
    def retrieve(state: RAGState) -> RAGState:
        t0 = time.time_ns()
        candidates, sub_spans = retriever.search(state["question"], k=TOP_K)
        span = {
            "name": "retrieve",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {
                "k": TOP_K,
                "candidates": len(candidates),
                "top_doc": candidates[0]["doc_id"] if candidates else "",
            },
            "children": sub_spans,
        }
        return {"candidates": candidates, "spans": state.get("spans", []) + [span]}

    def generate(state: RAGState) -> RAGState:
        t0 = time.time_ns()
        candidates = state.get("candidates", [])
        if candidates:
            answer = _best_sentence(state["question"], candidates[0]["chunk"])
        else:
            answer = "No relevant context found."
        span = {
            "name": "generate",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {"mode": "extractive", "answer_chars": len(answer)},
        }
        return {"answer": answer, "spans": state.get("spans", []) + [span]}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
