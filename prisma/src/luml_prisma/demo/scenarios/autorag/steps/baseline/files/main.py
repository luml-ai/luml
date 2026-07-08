"""Retrieval quality benchmark for the Nimbus docs RAG pipeline.

Runs the eval set through the LangGraph pipeline, tracks the experiment
(params, per-question metrics, traces, eval samples) with luml-sdk, packages
the graph as a LUML artifact, and reports results to the orchestrator via
.prisma/result.json.

Metric: recall_at_3 (share of relevant docs present in the top-3 retrieved
documents, averaged over questions) — higher is better.
"""

import json
import uuid
from pathlib import Path

from luml.experiments.tracker import ExperimentTracker
from luml.integrations.langgraph import save_langgraph

from rag.pipeline import TOP_K, build_graph
from rag.retrieval import PARAMS, STRATEGY, build_retriever

EXPERIMENTS_DIR = Path.home() / ".prisma" / "experiments"
EXPERIMENTS_DB = f"sqlite://{EXPERIMENTS_DIR}"
RESULT_PATH = Path(".prisma/result.json")
ARTIFACT_PATH = Path(".prisma/artifact.luml")


def _span_id() -> str:
    return uuid.uuid4().hex[:16]


def unique_doc_ids(candidates):
    seen, ordered = set(), []
    for cand in candidates:
        if cand["doc_id"] not in seen:
            seen.add(cand["doc_id"])
            ordered.append(cand["doc_id"])
    return ordered


def score_question(retrieved_ids, relevant_ids):
    relevant = set(relevant_ids)
    recall_3 = len(relevant & set(retrieved_ids[:3])) / len(relevant)
    recall_5 = len(relevant & set(retrieved_ids[:5])) / len(relevant)
    mrr = 0.0
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant:
            mrr = 1.0 / rank
            break
    return {"recall_at_3": recall_3, "recall_at_5": recall_5, "mrr": mrr}


def log_trace(tracker, trace_id, question_id, spans):
    root_id = _span_id()
    start = min(s["start"] for s in spans)
    end = max(s["end"] for s in spans)
    tracker.log_span(
        trace_id=trace_id,
        span_id=root_id,
        name=f"rag.query:{question_id}",
        start_time_unix_nano=start,
        end_time_unix_nano=end,
        attributes={"question_id": question_id, "strategy": STRATEGY},
    )
    _log_children(tracker, trace_id, root_id, spans)


def _log_children(tracker, trace_id, parent_id, spans):
    for span in spans:
        span_id = _span_id()
        tracker.log_span(
            trace_id=trace_id,
            span_id=span_id,
            name=span["name"],
            start_time_unix_nano=span["start"],
            end_time_unix_nano=span["end"],
            parent_span_id=parent_id,
            attributes=span.get("attributes", {}),
        )
        _log_children(tracker, trace_id, span_id, span.get("children", []))


def main() -> None:
    corpus = json.loads(Path("data/corpus.json").read_text())
    evalset = json.loads(Path("data/eval.json").read_text())
    documents = corpus["documents"]
    questions = evalset["questions"]
    dataset_id = evalset["dataset_id"]

    print(f"strategy={STRATEGY} docs={len(documents)} questions={len(questions)}")
    retriever = build_retriever(documents)
    graph = build_graph(retriever)

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    tracker = ExperimentTracker(EXPERIMENTS_DB)
    exp_id = tracker.start_experiment(
        name=f"autorag-{STRATEGY}",
        group="autorag",
        tags=["autorag", STRATEGY],
    )
    tracker.log_static("strategy", STRATEGY)
    for key, value in PARAMS.items():
        tracker.log_static(key, value)
    tracker.log_static("top_k", TOP_K)
    tracker.log_static("corpus_docs", len(documents))
    tracker.log_static("eval_dataset", dataset_id)

    totals = {"recall_at_3": 0.0, "recall_at_5": 0.0, "mrr": 0.0}
    for q in questions:
        trace_id = uuid.uuid4().hex
        state = graph.invoke({"question": q["question"]})
        retrieved_ids = unique_doc_ids(state.get("candidates", []))
        scores = score_question(retrieved_ids, q["relevant_doc_ids"])
        for key in totals:
            totals[key] += scores[key]

        log_trace(tracker, trace_id, q["id"], state.get("spans", []))
        tracker.log_eval_sample(
            eval_id=q["id"],
            dataset_id=dataset_id,
            inputs={"question": q["question"]},
            outputs={"answer": state.get("answer", ""), "retrieved_doc_ids": retrieved_ids},
            references={"relevant_doc_ids": q["relevant_doc_ids"]},
            scores=scores,
        )
        tracker.link_eval_sample_to_trace(dataset_id, q["id"], trace_id)
        print(
            f"  {q['id']} recall@3={scores['recall_at_3']:.2f} "
            f"mrr={scores['mrr']:.2f} top={retrieved_ids[:3]}"
        )

    n = len(questions)
    metrics = {
        "metric": round(totals["recall_at_3"] / n, 4),
        "recall_at_3": round(totals["recall_at_3"] / n, 4),
        "recall_at_5": round(totals["recall_at_5"] / n, 4),
        "mrr": round(totals["mrr"] / n, 4),
    }
    print(f"\nRESULTS {STRATEGY}: {metrics}")

    print("Packaging LangGraph pipeline as LUML artifact...")
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    model_ref = save_langgraph(
        lambda: build_graph(build_retriever(documents)),
        path=str(ARTIFACT_PATH),
        extra_dependencies=["scikit-learn"],
        extra_code_modules=["rag"],
        manifest_model_name="nimbus-rag",
        manifest_model_version=STRATEGY,
        manifest_model_description=(
            f"Nimbus docs RAG pipeline — {STRATEGY} "
            f"(recall@5={metrics['recall_at_5']:.3f})"
        ),
    )
    try:
        tracker.link_to_model(model_ref)
    except Exception as exc:  # linking is best-effort; upload also links server-side
        print(f"link_to_model skipped: {exc}")
    tracker.end_experiment(exp_id)

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps({
        "success": True,
        "experiment_id": exp_id,
        "metrics": metrics,
    }, indent=2))
    print(json.dumps({"type": "prisma-message", "metric": metrics["metric"]}))


if __name__ == "__main__":
    main()
