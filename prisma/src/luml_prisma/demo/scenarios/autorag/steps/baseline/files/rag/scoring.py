"""Per-question scorers for the support assistant benchmark."""

from rag.llm import keywords
from rag.text import tokenize


def unique_doc_ids(candidates: list[dict]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate["doc_id"] not in seen:
            seen.add(candidate["doc_id"])
            ordered.append(candidate["doc_id"])
    return ordered


def recall_at(retrieved: list[str], relevant: list[str], k: int) -> float:
    wanted = set(relevant)
    return len(wanted & set(retrieved[:k])) / len(wanted)


def mrr(retrieved: list[str], relevant: list[str]) -> float:
    wanted = set(relevant)
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in wanted:
            return 1.0 / rank
    return 0.0


def faithfulness(answer: str, passages: list[dict]) -> float:
    """Share of answer keywords that appear in the passages the answer was given."""
    claimed = keywords(answer)
    if not claimed:
        return 0.0
    context = set()
    for passage in passages:
        context.update(tokenize(passage["chunk"]))
    return len(claimed & context) / len(claimed)


def relevancy(question: str, answer: str) -> float:
    """Share of question keywords the answer addresses."""
    wanted = keywords(question)
    if not wanted:
        return 0.0
    return len(wanted & set(tokenize(answer))) / len(wanted)
