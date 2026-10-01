"""Span records built inside graph nodes and replayed into the tracker.

Graph nodes stay tracker-free so the compiled graph can be packaged; they
append plain dicts to the state and the eval harness turns them into spans.
"""

import time
import uuid


def span_id() -> str:
    return uuid.uuid4().hex[:16]


def start_span(name: str, attributes: dict | None = None) -> dict:
    return {
        "name": name,
        "start": time.time_ns(),
        "end": None,
        "attributes": dict(attributes or {}),
        "events": [],
        "children": [],
    }


def end_span(span: dict, **attributes) -> dict:
    span["attributes"].update(attributes)
    span["end"] = time.time_ns()
    return span


def add_event(span: dict, name: str, **attributes) -> None:
    span["events"].append(
        {"name": name, "time_unix_nano": time.time_ns(), "attributes": attributes}
    )


def replay(tracker, trace_id: str, spans: list[dict], parent_span_id: str | None) -> dict[str, str]:
    """Log a span tree; returns {span name: span id} for the top level."""
    ids: dict[str, str] = {}
    for span in spans:
        sid = span_id()
        ids[span["name"]] = sid
        tracker.log_span(
            trace_id=trace_id,
            span_id=sid,
            name=span["name"],
            start_time_unix_nano=span["start"],
            end_time_unix_nano=span["end"] or time.time_ns(),
            parent_span_id=parent_span_id,
            attributes=span.get("attributes") or None,
            events=span.get("events") or None,
        )
        replay(tracker, trace_id, span.get("children", []), sid)
    return ids
