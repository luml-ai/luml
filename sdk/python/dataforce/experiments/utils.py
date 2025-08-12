from enum import Enum


class SpanType(Enum):
    DEFAULT = 0
    CHAT = 1
    AGENT = 2
    TOOL = 3
    EMBEDDER = 4
    RERANKER = 5


def guess_span_type(attributes: dict) -> SpanType:
    if attributes.get("llm.request.type", "") == "chat":
        return SpanType.CHAT
    if attributes.get("gen_ai.operation.name", "") == "chat":
        return SpanType.CHAT
    if attributes.get("gen_ai.operation.name", "") == "invoke_agent":
        return SpanType.AGENT
    if attributes.get("gen_ai.operation.name", "") == "execute_tool":
        return SpanType.TOOL
    if attributes.get("gen_ai.operation.name", "") == "embeddings":
        return SpanType.EMBEDDER

    return SpanType.DEFAULT
