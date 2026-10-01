"""LangGraph support assistant: rewrite -> retrieve -> rerank -> generate -> verify.

Nodes stay tracker-free so the compiled graph can be packaged with
save_langgraph; each node records its span into the state and the eval
harness replays the spans as a trace.
"""

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from rag.llm import SimulatedChatModel, chat_attributes, keywords
from rag.text import tokenize
from rag.tracing import add_event, end_span, start_span

TOP_K = 5
RERANK_KEEP = 3
AGENT_NAME = "nimbus-support-assistant"


class RAGState(TypedDict, total=False):
    question: str
    search_query: str
    candidates: list[dict[str, Any]]
    reranked: list[dict[str, Any]]
    answer: str
    citations: list[str]
    citations_valid: bool
    usage: dict[str, int]
    spans: list[dict[str, Any]]


def _with_span(state: RAGState, span: dict) -> list[dict]:
    return state.get("spans", []) + [span]


def _add_usage(state: RAGState, result) -> dict[str, int]:
    usage = dict(state.get("usage", {"input_tokens": 0, "output_tokens": 0}))
    usage["input_tokens"] += result.input_tokens
    usage["output_tokens"] += result.output_tokens
    return usage


def build_graph(retriever, llm: SimulatedChatModel | None = None):
    llm = llm or SimulatedChatModel()
    known_docs = set(retriever.chunk_doc_ids)

    def rewrite(state: RAGState) -> RAGState:
        span = start_span("llm.rewrite_query")
        result = llm.rewrite(state["question"])
        end_span(span, **chat_attributes(llm, result))
        return {
            "search_query": result.text,
            "usage": _add_usage(state, result),
            "spans": _with_span(state, span),
        }

    def retrieve(state: RAGState) -> RAGState:
        span = start_span(
            "retrieve",
            {"gen_ai.operation.name": "embeddings", "retrieval.k": TOP_K,
             "retrieval.query": state["search_query"]},
        )
        candidates, sub_spans = retriever.search(state["search_query"], k=TOP_K)
        span["children"] = sub_spans
        end_span(
            span,
            **{
                "retrieval.documents": json.dumps(
                    [{"doc_id": c["doc_id"], "score": round(c["score"], 4)} for c in candidates]
                ),
                "retrieval.candidates": len(candidates),
            },
        )
        return {"candidates": candidates, "spans": _with_span(state, span)}

    def rerank(state: RAGState) -> RAGState:
        span = start_span(
            "rerank",
            {"reranker": "lexical-overlap", "candidates_in": len(state.get("candidates", [])),
             "keep": RERANK_KEEP},
        )
        wanted = keywords(state["question"]) | keywords(state["search_query"])
        scored = []
        for rank, candidate in enumerate(state.get("candidates", [])):
            overlap = len(wanted & set(tokenize(candidate["chunk"]))) / max(1, len(wanted))
            scored.append((0.6 * overlap + 0.4 / (1 + rank), candidate))
        scored.sort(key=lambda item: -item[0])
        reranked = [
            {**candidate, "rerank_score": round(score, 4)} for score, candidate in scored
        ][:RERANK_KEEP]
        end_span(span, kept=[c["doc_id"] for c in reranked])
        return {"reranked": reranked, "spans": _with_span(state, span)}

    def generate(state: RAGState) -> RAGState:
        span = start_span("llm.generate_answer")
        passages = state.get("reranked", [])
        result = llm.answer(state["question"], passages)
        add_event(span, "gen_ai.choice", index=0, finish_reason=result.finish_reason)
        end_span(span, **chat_attributes(llm, result))
        citations = [
            token.strip("[]") for token in result.text.split() if token.startswith("[doc-")
        ]
        return {
            "answer": result.text,
            "citations": citations,
            "usage": _add_usage(state, result),
            "spans": _with_span(state, span),
        }

    def verify_citations(state: RAGState) -> RAGState:
        citations = state.get("citations", [])
        span = start_span(
            "tool.lookup_doc",
            {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "lookup_doc",
             "gen_ai.tool.call.arguments": json.dumps({"doc_ids": citations})},
        )
        found = [doc_id for doc_id in citations if doc_id in known_docs]
        missing = [doc_id for doc_id in citations if doc_id not in known_docs]
        end_span(
            span,
            **{"gen_ai.tool.call.result": json.dumps({"found": found, "missing": missing})},
        )
        return {"citations_valid": bool(found) and not missing, "spans": _with_span(state, span)}

    graph = StateGraph(RAGState)
    graph.add_node("rewrite", rewrite)
    graph.add_node("retrieve", retrieve)
    graph.add_node("rerank", rerank)
    graph.add_node("generate", generate)
    graph.add_node("verify_citations", verify_citations)
    graph.add_edge(START, "rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "generate")
    graph.add_edge("generate", "verify_citations")
    graph.add_edge("verify_citations", END)
    return graph.compile()
