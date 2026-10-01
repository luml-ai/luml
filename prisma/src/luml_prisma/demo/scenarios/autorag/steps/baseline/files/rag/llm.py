"""Deterministic stand-in for the support assistant's chat model.

The benchmark runs offline and reproducibly: answers are extracted from the
retrieved passages and phrased with fixed templates, token usage is estimated,
and every call reports the same gen_ai.* attributes a provider span carries.
"""

import json
from dataclasses import dataclass

from rag.text import tokenize

MODEL_NAME = "nimbus-support-sim-1"
PROVIDER = "nimbus-sim"
TEMPERATURE = 0.0
MAX_PASSAGES = 3

SYSTEM_PROMPT = (
    "You are the Nimbus Analytics support assistant. Answer from the provided "
    "documentation passages only, cite the passage id in square brackets, and say "
    "when the documentation does not cover the question."
)
REWRITE_PROMPT = (
    "Rewrite the user question into a documentation search query. Expand product "
    "abbreviations and keep every technical token unchanged."
)
ABBREVIATIONS = {
    "sso": "sso single sign-on",
    "2fa": "2fa two-factor authentication",
    "mfa": "mfa multi-factor authentication",
    "nql": "nql nimbus query language",
    "gdpr": "gdpr data retention",
}
STOPWORDS = frozenset(
    "a an the of to in on for with and or is are be how do does can i my we what "
    "which when where why it this that from by as at into if you your".split()
)


@dataclass
class ChatResult:
    text: str
    messages: list[dict]
    input_tokens: int
    output_tokens: int
    finish_reason: str = "stop"


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


def keywords(text: str) -> set[str]:
    return {token for token in tokenize(text) if token not in STOPWORDS}


def best_sentence(question: str, passage: str) -> str:
    wanted = keywords(question)
    sentences = [s.strip() for s in passage.replace("\n", " ").split(". ") if s.strip()]
    if not sentences:
        return passage.strip()
    chosen = max(sentences, key=lambda s: len(wanted & set(tokenize(s))))
    return chosen if chosen.endswith(".") else chosen + "."


class SimulatedChatModel:
    def __init__(self, model: str = MODEL_NAME, temperature: float = TEMPERATURE) -> None:
        self.model = model
        self.temperature = temperature

    def rewrite(self, question: str) -> ChatResult:
        messages = [
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": question},
        ]
        tokens = tokenize(question)
        expanded = [ABBREVIATIONS.get(token, token) for token in tokens]
        query = question if expanded == tokens else " ".join(expanded)
        return self._complete(messages, query)

    def answer(self, question: str, passages: list[dict]) -> ChatResult:
        shown = passages[:MAX_PASSAGES]
        context = "\n\n".join(
            f"[{p['doc_id']}] {p['chunk']}" for p in shown
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}\n\nPassages:\n{context}"},
        ]
        if not shown:
            return self._complete(messages, "The documentation does not cover this question.")
        wanted = keywords(question)
        grounded = [
            p for p in shown if wanted & set(tokenize(p["chunk"]))
        ] or shown[:1]
        lead = grounded[0]
        text = f"{best_sentence(question, lead['chunk'])} [{lead['doc_id']}]"
        if len(grounded) > 1 and grounded[1]["doc_id"] != lead["doc_id"]:
            second = grounded[1]
            text += f" See also: {best_sentence(question, second['chunk'])} [{second['doc_id']}]"
        return self._complete(messages, text)

    def _complete(self, messages: list[dict], text: str) -> ChatResult:
        prompt = "\n".join(m["content"] for m in messages)
        return ChatResult(
            text=text,
            messages=messages,
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(text),
        )


def chat_attributes(model: SimulatedChatModel, result: ChatResult) -> dict:
    """gen_ai.* attributes in the shape the OpenAI instrumentation emits."""
    return {
        "gen_ai.operation.name": "chat",
        "gen_ai.system": PROVIDER,
        "gen_ai.request.model": model.model,
        "gen_ai.request.temperature": model.temperature,
        "gen_ai.response.model": model.model,
        "gen_ai.response.finish_reasons": [result.finish_reason],
        "gen_ai.usage.input_tokens": result.input_tokens,
        "gen_ai.usage.output_tokens": result.output_tokens,
        "gen_ai.input.messages": json.dumps(result.messages),
        "gen_ai.output.messages": json.dumps(
            [{"role": "assistant", "content": result.text}]
        ),
    }
