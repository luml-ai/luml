from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class InferenceEvent:
    event_id: str
    deployment_id: str
    status: str
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    status_code: int | None = None
    inputs: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "event_id": self.event_id,
            "deployment_id": self.deployment_id,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }
        if self.status_code is not None:
            d["status_code"] = self.status_code
        if self.inputs is not None:
            d["inputs"] = self.inputs
        if self.output is not None:
            d["output"] = self.output
        if self.error is not None:
            d["error"] = self.error
        if self.trace_id is not None:
            d["trace_id"] = self.trace_id
        if self.span_id is not None:
            d["span_id"] = self.span_id
        return d
