import json
import logging
import random
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from opentelemetry import propagate, trace
from opentelemetry.trace import Span

from luml_satellite.monitoring.ingest.events import InferenceEvent
from luml_satellite.monitoring.ingest.telemetry import TelemetrySetup
from luml_satellite.workload import InferenceOutcome, RecordingPolicy, RecordingSession

logger = logging.getLogger(__name__)


def _generate_event_id() -> str:
    return str(uuid.uuid7())


def _inject_trace_context(span: Span | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    try:
        span_context = trace.set_span_in_context(span) if span is not None else None
        propagate.inject(headers, context=span_context)
    except Exception:
        logger.warning("Failed to inject trace context", exc_info=True)
    return headers


def _encoded_size(value: object) -> int | None:
    try:
        return len(json.dumps(value, separators=(",", ":")).encode())
    except TypeError, ValueError:
        return None


class _InstrumentationSession:
    def __init__(
        self,
        instrumentation: InferenceInstrumentation,
        deployment_id: str,
        inputs: object | None,
        policy: RecordingPolicy,
        random_value: float,
    ) -> None:
        self._instrumentation = instrumentation
        self._deployment_id = deployment_id
        self._policy = policy
        self._event_id = _generate_event_id()
        self._span = instrumentation._start_span(deployment_id, self._event_id)
        self._upstream_headers = _inject_trace_context(self._span)
        input_size = _encoded_size(inputs) if inputs is not None else None
        self._bodies_sampled = (
            inputs is not None
            and input_size is not None
            and input_size <= policy.body_max_bytes
            and policy.captures_bodies(random_value)
        )
        self._inputs = inputs if self._bodies_sampled and policy.keep_inputs else None
        self._completed = False

    @property
    def event_id(self) -> str:
        return self._event_id

    @property
    def upstream_headers(self) -> Mapping[str, str]:
        return self._upstream_headers

    async def complete(self, outcome: InferenceOutcome) -> None:
        if self._completed:
            return
        self._completed = True

        succeeded = outcome.error is None and 200 <= outcome.status_code < 400
        output_size = _encoded_size(outcome.output) if outcome.output is not None else None
        output = (
            outcome.output
            if self._bodies_sampled
            and self._policy.keep_outputs
            and output_size is not None
            and output_size <= self._policy.body_max_bytes
            else None
        )
        trace_id, span_id = self._finish_span(outcome, succeeded=succeeded)
        self._instrumentation._record(
            InferenceEvent(
                event_id=self._event_id,
                deployment_id=self._deployment_id,
                status="success" if succeeded else "error",
                status_code=outcome.status_code,
                latency_ms=outcome.latency_ms,
                timestamp=datetime.now(UTC).isoformat(),
                inputs=self._inputs,
                output=output,
                error=outcome.error,
                trace_id=trace_id,
                span_id=span_id,
                bodies_sampled=self._bodies_sampled,
            )
        )

    def _finish_span(
        self, outcome: InferenceOutcome, *, succeeded: bool
    ) -> tuple[str | None, str | None]:
        if self._span is None:
            return None, None
        trace_id = None
        span_id = None
        try:
            span_context = self._span.get_span_context()
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")
            if succeeded:
                self._span.set_status(trace.StatusCode.OK)
            else:
                self._span.set_status(trace.StatusCode.ERROR, outcome.error)
        except Exception:
            logger.warning("Failed to finish inference span", exc_info=True)
        finally:
            try:
                self._span.end()
            except Exception:
                logger.warning("Failed to end inference span", exc_info=True)
        return trace_id, span_id


class InferenceInstrumentation:
    def __init__(
        self,
        telemetry: TelemetrySetup,
        *,
        random_source: Callable[[], float] = random.random,
    ) -> None:
        self._telemetry = telemetry
        self._tracer = telemetry.tracer()
        self._metrics = telemetry.inference_metrics()
        self._random_source = random_source

    async def start(
        self,
        deployment_id: str,
        inputs: object | None,
        policy: RecordingPolicy,
    ) -> RecordingSession:
        return _InstrumentationSession(
            self,
            deployment_id,
            inputs,
            policy,
            self._random_source(),
        )

    async def instrumented_compute(
        self,
        deployment_id: str,
        safe_inputs: dict[str, Any] | None,
        forward_fn: Callable[..., Awaitable[dict[str, Any]]],
    ) -> tuple[dict[str, Any], str]:
        session = await self.start(deployment_id, safe_inputs, RecordingPolicy())
        started_at = time.monotonic()
        try:
            result = await forward_fn(extra_headers=dict(session.upstream_headers))
        except Exception as error:
            raw_status_code = getattr(error, "status_code", None)
            status_code = raw_status_code if isinstance(raw_status_code, int) else 500
            await session.complete(
                InferenceOutcome(
                    status_code=status_code,
                    latency_ms=(time.monotonic() - started_at) * 1000,
                    error=str(error),
                )
            )
            raise
        await session.complete(
            InferenceOutcome(
                status_code=200,
                latency_ms=(time.monotonic() - started_at) * 1000,
                output=result,
            )
        )
        return result, session.event_id or ""

    def _start_span(self, deployment_id: str, event_id: str) -> Span | None:
        try:
            return self._tracer.start_span(
                "inference",
                attributes={"deployment_id": deployment_id, "event_id": event_id},
            )
        except Exception:
            logger.warning("Failed to start inference span", exc_info=True)
            return None

    def _record(self, event: InferenceEvent) -> None:
        try:
            self._metrics.request_counter.add(
                1, {"deployment_id": event.deployment_id, "status": event.status}
            )
            self._metrics.latency_histogram.record(
                event.latency_ms,
                {"deployment_id": event.deployment_id, "status": event.status},
            )
            if event.status != "success" and event.status_code is not None:
                self._metrics.error_counter.add(
                    1,
                    {
                        "deployment_id": event.deployment_id,
                        "status_code": event.status_code,
                    },
                )
        except Exception:
            logger.warning("Failed to record inference metrics", exc_info=True)
        self._telemetry.emit_event(event)
