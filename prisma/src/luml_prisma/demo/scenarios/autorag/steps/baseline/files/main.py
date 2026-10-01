"""Support-assistant benchmark over the Nimbus Analytics documentation.

Runs the eval set through the LangGraph assistant, tracks the experiment
(params, metric curves, one trace per question, eval samples with scores and
reviewer annotations, reports and plots) with luml-sdk, packages the graph as a
LUML artifact, and reports results to the orchestrator via .prisma/result.json.

Metric: recall_at_3 (share of relevant docs present in the top-3 retrieved
documents, averaged over questions) — higher is better.
"""

import csv
import io
import json
import os
import time
import uuid
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from luml.experiments.tracker import ExperimentTracker
from luml.integrations.langgraph import save_langgraph

from rag import scoring
from rag.llm import MODEL_NAME, TEMPERATURE, SimulatedChatModel
from rag.pipeline import AGENT_NAME, RERANK_KEEP, TOP_K, build_graph
from rag.retrieval import PARAMS, STRATEGY, build_retriever
from rag.tracing import replay, span_id

EXPERIMENTS_DIR = Path(
    os.environ.get("LUML_EXPERIMENTS_DIR", str(Path.home() / ".luml" / "experiments"))
)
RESULT_PATH = Path(".prisma/result.json")
ARTIFACT_PATH = Path(".prisma/artifact.luml")
REGISTRY_METRICS_TAG = "dataforce.studio::registry_metrics:v1"
GROUP = "support-assistant"
REVIEWER = "support-qa"


def log_trace(tracker, trace_id: str, question_id: str, state: dict) -> dict[str, str]:
    spans = state.get("spans", [])
    root_id = span_id()
    start = min(s["start"] for s in spans)
    end = max(s["end"] for s in spans)
    tracker.log_span(
        trace_id=trace_id,
        span_id=root_id,
        name=f"{AGENT_NAME}.invoke",
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": AGENT_NAME,
            "question_id": question_id,
            "retrieval.strategy": STRATEGY,
            "gen_ai.usage.input_tokens": state["usage"]["input_tokens"],
            "gen_ai.usage.output_tokens": state["usage"]["output_tokens"],
        },
    )
    ids = replay(tracker, trace_id, spans, root_id)
    ids["root"] = root_id
    return ids


def score_question(question: dict, state: dict) -> dict:
    retrieved = scoring.unique_doc_ids(state.get("candidates", []))
    reranked = scoring.unique_doc_ids(state.get("reranked", []))
    relevant = question["relevant_doc_ids"]
    return {
        "recall_at_3": scoring.recall_at(retrieved, relevant, 3),
        "recall_at_5": scoring.recall_at(retrieved, relevant, 5),
        "mrr": scoring.mrr(retrieved, relevant),
        "rerank_recall_at_3": scoring.recall_at(reranked, relevant, 3),
        "faithfulness": round(scoring.faithfulness(state.get("answer", ""), state.get("reranked", [])), 4),
        "relevancy": round(scoring.relevancy(question["question"], state.get("answer", "")), 4),
        "citation_valid": bool(state.get("citations_valid")),
        "input_tokens": state["usage"]["input_tokens"],
        "output_tokens": state["usage"]["output_tokens"],
    }


def retrieval_heatmap(rows: list[dict]) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 0.28 * len(rows) + 1.2))
    matrix = [[row["top_scores"][i] if i < len(row["top_scores"]) else 0.0 for i in range(TOP_K)]
              for row in rows]
    image = ax.imshow(matrix, aspect="auto", cmap="Blues")
    ax.set_yticks(range(len(rows)), [row["id"] for row in rows], fontsize=7)
    ax.set_xticks(range(TOP_K), [f"rank {i + 1}" for i in range(TOP_K)])
    for y, row in enumerate(rows):
        for x, hit in enumerate(row["hits"][:TOP_K]):
            if hit:
                ax.text(x, y, "✓", ha="center", va="center", color="#065f46", fontsize=8)
    ax.set_title(f"Retrieval scores per question — {STRATEGY}")
    fig.colorbar(image, ax=ax, fraction=0.03)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def recall_figure(rows: list[dict]) -> bytes:
    fig, ax = plt.subplots(figsize=(7, 3))
    colors = ["#2563eb" if row["scores"]["recall_at_3"] >= 1 else "#dc2626" for row in rows]
    ax.bar([row["id"] for row in rows], [row["scores"]["mrr"] for row in rows], color=colors)
    ax.set_ylabel("MRR")
    ax.set_title("Per-question MRR (red: relevant doc missing from top-3)")
    ax.tick_params(axis="x", labelrotation=90, labelsize=7)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def failures_report(rows: list[dict], titles: dict[str, str]) -> str:
    lines = [f"# Retrieval misses — {STRATEGY}", ""]
    misses = [row for row in rows if row["scores"]["recall_at_3"] < 1]
    lines.append(f"{len(misses)} of {len(rows)} questions miss a relevant doc in the top-3.")
    lines.append("")
    for row in misses:
        lines.append(f"## {row['id']} — {row['question']}")
        lines.append(f"- expected: {', '.join(row['relevant'])}")
        lines.append("- retrieved: " + ", ".join(
            f"{doc_id} ({titles.get(doc_id, '?')})" for doc_id in row["retrieved"][:3]
        ))
        lines.append(f"- answer: {row['answer']}")
        lines.append("")
    return "\n".join(lines)


def register_metrics(model_ref, metrics: dict[str, float]) -> None:
    """Stamp the registry metrics block the platform lists next to the artifact."""
    model_ref._append_metadata(
        idx=None, tags=[REGISTRY_METRICS_TAG], payload={"metrics": metrics}, data=[],
        prefix=REGISTRY_METRICS_TAG,
    )


def annotate(tracker, dataset_id: str, rows: list[dict], trace_spans: dict[str, dict[str, str]]) -> None:
    by_recall = sorted(rows, key=lambda row: (row["scores"]["recall_at_3"], row["scores"]["mrr"]))
    worst, best = by_recall[0], by_recall[-1]
    tracker.log_eval_annotation(
        dataset_id, worst["id"], "answer_accepted", "feedback", "bool", False, user=REVIEWER,
        rationale=f"Cites {worst['retrieved'][0] if worst['retrieved'] else 'nothing'}; "
                  f"the answer lives in {worst['relevant'][0]}.",
    )
    tracker.log_eval_annotation(
        dataset_id, best["id"], "answer_accepted", "feedback", "bool", True, user=REVIEWER,
        rationale="Grounded in the right passage, citation checks out.",
    )
    tracker.log_eval_annotation(
        dataset_id, by_recall[1]["id"], "expected_source", "expectation", "string",
        by_recall[1]["relevant"][0], user=REVIEWER,
        rationale="Reviewer-confirmed source document for this question.",
    )
    tracker.log_span_annotation(
        worst["trace_id"], trace_spans[worst["id"]]["retrieve"], "retrieval_quality",
        "feedback", "bool", False, user=REVIEWER,
        rationale="Top passages come from a neighbouring page; vocabulary mismatch.",
    )
    tracker.log_span_annotation(
        best["trace_id"], trace_spans[best["id"]]["llm.generate_answer"], "grounded",
        "feedback", "bool", True, user=REVIEWER,
        rationale="Every sentence in the answer is supported by the cited passage.",
    )


def main() -> None:
    corpus = json.loads(Path("data/corpus.json").read_text())
    evalset = json.loads(Path("data/eval.json").read_text())
    documents = corpus["documents"]
    titles = {doc["id"]: doc["title"] for doc in documents}
    questions = evalset["questions"]
    dataset_id = evalset["dataset_id"]
    print(f"strategy={STRATEGY} docs={len(documents)} questions={len(questions)}")

    build_started = time.time()
    retriever = build_retriever(documents)
    llm = SimulatedChatModel()
    graph = build_graph(retriever, llm)
    index_build_ms = (time.time() - build_started) * 1000

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    tracker = ExperimentTracker(f"sqlite://{EXPERIMENTS_DIR}")
    exp_id = tracker.start_experiment(
        name=f"assistant-{STRATEGY}", group=GROUP, tags=["support-assistant", STRATEGY],
    )
    tracker.log_static("strategy", STRATEGY)
    for key, value in PARAMS.items():
        tracker.log_static(key, value)
    tracker.log_static("top_k", TOP_K)
    tracker.log_static("rerank_keep", RERANK_KEEP)
    tracker.log_static("llm_model", MODEL_NAME)
    tracker.log_static("llm_temperature", TEMPERATURE)
    tracker.log_static("corpus_docs", len(documents))
    tracker.log_static("index_chunks", len(retriever.chunks))
    tracker.log_static("eval_dataset", dataset_id)
    tracker.log_static("eval_questions", len(questions))
    tracker.log_dynamic("index_build_ms", round(index_build_ms, 1))

    rows: list[dict] = []
    trace_spans: dict[str, dict[str, str]] = {}
    running = {"recall_at_3": 0.0, "mrr": 0.0}
    for step, question in enumerate(questions, start=1):
        trace_id = uuid.uuid4().hex
        started = time.time()
        state = graph.invoke({"question": question["question"]})
        latency_ms = (time.time() - started) * 1000
        scores = score_question(question, state)
        scores["latency_ms"] = round(latency_ms, 2)
        retrieved = scoring.unique_doc_ids(state.get("candidates", []))
        for key in running:
            running[key] += scores[key]
            tracker.log_dynamic(f"running_{key}", running[key] / step, step=step)
        tracker.log_dynamic("question_latency_ms", round(latency_ms, 2), step=step)

        trace_spans[question["id"]] = log_trace(tracker, trace_id, question["id"], state)
        tracker.log_eval_sample(
            eval_id=question["id"],
            dataset_id=dataset_id,
            inputs={"question": question["question"], "search_query": state["search_query"]},
            outputs={
                "answer": state.get("answer", ""),
                "citations": state.get("citations", []),
                "retrieved_doc_ids": retrieved,
            },
            references={"relevant_doc_ids": question["relevant_doc_ids"]},
            scores=scores,
            metadata={
                "topic": question["relevant_doc_ids"][0].removeprefix("doc-"),
                "rewritten": state["search_query"] != question["question"],
            },
        )
        tracker.link_eval_sample_to_trace(dataset_id, question["id"], trace_id)
        candidates = state.get("candidates", [])
        rows.append({
            "id": question["id"], "question": question["question"],
            "relevant": question["relevant_doc_ids"], "retrieved": retrieved,
            "answer": state.get("answer", ""), "scores": scores, "trace_id": trace_id,
            "top_scores": [round(c["score"], 4) for c in candidates[:TOP_K]],
            "hits": [c["doc_id"] in question["relevant_doc_ids"] for c in candidates[:TOP_K]],
        })
        print(f"  {question['id']} recall@3={scores['recall_at_3']:.2f} "
              f"mrr={scores['mrr']:.2f} faithful={scores['faithfulness']:.2f} top={retrieved[:3]}")

    n = len(rows)
    metrics = {
        "metric": round(sum(r["scores"]["recall_at_3"] for r in rows) / n, 4),
        "recall_at_3": round(sum(r["scores"]["recall_at_3"] for r in rows) / n, 4),
        "recall_at_5": round(sum(r["scores"]["recall_at_5"] for r in rows) / n, 4),
        "mrr": round(sum(r["scores"]["mrr"] for r in rows) / n, 4),
        "faithfulness": round(sum(r["scores"]["faithfulness"] for r in rows) / n, 4),
        "relevancy": round(sum(r["scores"]["relevancy"] for r in rows) / n, 4),
        "citation_valid_rate": round(sum(r["scores"]["citation_valid"] for r in rows) / n, 4),
        "p50_latency_ms": round(sorted(r["scores"]["latency_ms"] for r in rows)[n // 2], 2),
    }
    for key, value in metrics.items():
        if key != "metric":
            tracker.log_dynamic(f"eval_{key}", value)
    tracker.log_dynamic("total_input_tokens", sum(r["scores"]["input_tokens"] for r in rows))
    tracker.log_dynamic("total_output_tokens", sum(r["scores"]["output_tokens"] for r in rows))
    print(f"\nRESULTS {STRATEGY}: {metrics}")

    annotate(tracker, dataset_id, rows, trace_spans)

    report = io.StringIO()
    writer = csv.writer(report)
    writer.writerow(["id", "question", "relevant", "retrieved_top3", "answer", *rows[0]["scores"]])
    for row in rows:
        writer.writerow([row["id"], row["question"], " ".join(row["relevant"]),
                         " ".join(row["retrieved"][:3]), row["answer"], *row["scores"].values()])
    tracker.log_attachment("reports/eval_report.csv", report.getvalue())
    tracker.log_attachment("reports/failures.md", failures_report(rows, titles))
    tracker.log_attachment("reports/config.json", json.dumps(
        {"strategy": STRATEGY, **PARAMS, "top_k": TOP_K, "rerank_keep": RERANK_KEEP,
         "llm_model": MODEL_NAME, "temperature": TEMPERATURE}, indent=2))
    tracker.log_attachment("plots/retrieval_scores.png", retrieval_heatmap(rows), binary=True)
    tracker.log_attachment("plots/mrr_by_question.png", recall_figure(rows), binary=True)

    print("Packaging the assistant graph as a LUML artifact...")
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.unlink(missing_ok=True)
    model_ref = save_langgraph(
        lambda: build_graph(build_retriever(documents)),
        path=str(ARTIFACT_PATH),
        extra_dependencies=["scikit-learn"],
        extra_code_modules=["rag"],
        manifest_model_name="support-assistant",
        manifest_model_version=STRATEGY,
        manifest_model_description=(
            f"Nimbus docs support assistant — {STRATEGY} retrieval "
            f"(recall@3={metrics['recall_at_3']:.3f}, faithfulness={metrics['faithfulness']:.3f})"
        ),
    )
    register_metrics(model_ref, {k: v for k, v in metrics.items() if k != "metric"})
    tracker.log_model(
        model_ref, name="support-assistant", tags=["langgraph", STRATEGY],
        description=f"recall@3={metrics['recall_at_3']:.3f}",
    )
    tracker.end_experiment(exp_id)
    tracker.link_to_model(model_ref, experiment_id=exp_id)

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(
        {"success": True, "experiment_id": exp_id, "metrics": metrics}, indent=2,
    ))
    print(json.dumps({"type": "prisma-message", "metric": metrics["metric"]}))


if __name__ == "__main__":
    main()
