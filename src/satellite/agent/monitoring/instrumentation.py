import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from opentelemetry import context, propagate, trace

from agent.monitoring.events import InferenceEvent
from agent.monitoring.telemetry import TelemetrySetup

logger = logging.getLogger(__name__)


def _generate_event_id() -> str:
    return str(uuid.uuid7())


def _inject_trace_context() -> dict[str, str]:
    headers: dict[str, str] = {}
    try:
        propagate.inject(headers, context=context.get_current())
    except Exception:
        logger.warning("Failed to inject trace context", exc_info=True)
    return headers


class InferenceInstrumentation:
    def __init__(self, telemetry: TelemetrySetup) -> None:
        self._telemetry = telemetry
        self._tracer = telemetry.tracer()
        self._metrics = telemetry.inference_metrics()

    async def instrumented_compute(
        self,
        deployment_id: str,
        safe_inputs: dict[str, Any] | None,
        forward_fn: Callable[..., Awaitable[dict]],
    ) -> tuple[dict, str]:
        event_id = _generate_event_id()
        start = time.monotonic()
        span = None
        try:
            span = self._tracer.start_span(
                "inference",
                attributes={
                    "deployment_id": deployment_id,
                    "event_id": event_id,
                },
            )
        except Exception:
            logger.warning("Failed to start inference span", exc_info=True)

        ctx = trace.set_span_in_context(span) if span else None
        token = context.attach(ctx) if ctx else None

        try:
            propagation_headers = _inject_trace_context()
            result = await forward_fn(extra_headers=propagation_headers)
            latency_ms = (time.monotonic() - start) * 1000

            trace_id = None
            span_id = None
            if span:
                try:
                    sc = span.get_span_context()
                    trace_id = format(sc.trace_id, "032x")
                    span_id = format(sc.span_id, "016x")
                    span.set_status(trace.StatusCode.OK)
                except Exception:
                    logger.warning("Failed to read span context", exc_info=True)

            self._record_success(
                event_id=event_id,
                deployment_id=deployment_id,
                latency_ms=latency_ms,
                safe_inputs=safe_inputs,
                output=result,
                trace_id=trace_id,
                span_id=span_id,
            )
            return result, event_id

        except Exception as exc:
            latency_ms = (time.monotonic() - start) * 1000

            trace_id = None
            span_id = None
            if span:
                try:
                    sc = span.get_span_context()
                    trace_id = format(sc.trace_id, "032x")
                    span_id = format(sc.span_id, "016x")
                    span.set_status(trace.StatusCode.ERROR, str(exc))
                    span.record_exception(exc)
                except Exception:
                    logger.warning("Failed to record span error", exc_info=True)

            self._record_error(
                event_id=event_id,
                deployment_id=deployment_id,
                latency_ms=latency_ms,
                safe_inputs=safe_inputs,
                error=exc,
                trace_id=trace_id,
                span_id=span_id,
            )
            raise

        finally:
            if span:
                try:
                    span.end()
                except Exception:
                    logger.warning("Failed to end span", exc_info=True)
            if token is not None:
                with suppress(Exception):
                    context.detach(token)

    def _record_success(
        self,
        *,
        event_id: str,
        deployment_id: str,
        latency_ms: float,
        safe_inputs: dict[str, Any] | None,
        output: dict,
        trace_id: str | None,
        span_id: str | None,
    ) -> None:
        try:
            self._metrics.request_counter.add(
                1, {"deployment_id": deployment_id, "status": "success"}
            )
            self._metrics.latency_histogram.record(
                latency_ms, {"deployment_id": deployment_id, "status": "success"}
            )
        except Exception:
            logger.warning("Failed to record success metrics", exc_info=True)

        try:
            event = InferenceEvent(
                event_id=event_id,
                deployment_id=deployment_id,
                status="success",
                latency_ms=latency_ms,
                timestamp=datetime.now(UTC).isoformat(),
                inputs=safe_inputs,
                output=output,
                trace_id=trace_id,
                span_id=span_id,
            )
            self._telemetry.emit_event(event)
        except Exception:
            logger.warning("Failed to emit success event", exc_info=True)

    def _record_error(
        self,
        *,
        event_id: str,
        deployment_id: str,
        latency_ms: float,
        safe_inputs: dict[str, Any] | None,
        error: Exception,
        trace_id: str | None,
        span_id: str | None,
    ) -> None:
        from agent.clients.model_server_client import ModelServerError

        status_code: int | None = None
        if isinstance(error, ModelServerError):
            status_code = error.status_code

        try:
            self._metrics.request_counter.add(
                1, {"deployment_id": deployment_id, "status": "error"}
            )
            self._metrics.latency_histogram.record(
                latency_ms, {"deployment_id": deployment_id, "status": "error"}
            )
            if status_code is not None:
                self._metrics.error_counter.add(
                    1, {"deployment_id": deployment_id, "status_code": status_code}
                )
        except Exception:
            logger.warning("Failed to record error metrics", exc_info=True)

        try:
            event = InferenceEvent(
                event_id=event_id,
                deployment_id=deployment_id,
                status="error",
                latency_ms=latency_ms,
                timestamp=datetime.now(UTC).isoformat(),
                status_code=status_code,
                inputs=safe_inputs,
                error=str(error),
                trace_id=trace_id,
                span_id=span_id,
            )
            self._telemetry.emit_event(event)
        except Exception:
            logger.warning("Failed to emit error event", exc_info=True)
