import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)

_TRACER_NAME = "satellite-model-server"

try:
    from opentelemetry import trace
    from opentelemetry.propagate import extract
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
    )
    from opentelemetry.trace import StatusCode

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


def _create_tracer() -> Any:  # noqa: ANN401
    if not _HAS_OTEL:
        return None

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return None

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        resource = Resource.create({"service.name": _TRACER_NAME})
        provider = SDKTracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        return provider.get_tracer(_TRACER_NAME)
    except Exception:
        logger.warning("Failed to initialize model-server telemetry", exc_info=True)
        return None


_tracer: Any = None  # noqa: ANN401
_initialized = False


def _get_tracer() -> Any:  # noqa: ANN401
    global _tracer, _initialized
    if not _initialized:
        _tracer = _create_tracer()
        _initialized = True
    return _tracer


def extract_context(headers: dict[str, str]) -> Any:  # noqa: ANN401
    if not _HAS_OTEL:
        return None
    try:
        return extract(headers)
    except Exception:
        logger.warning("Failed to extract trace context", exc_info=True)
        return None


@asynccontextmanager
async def model_span(
    headers: dict[str, str],
) -> AsyncGenerator[None]:
    tracer = _get_tracer()
    if tracer is None:
        yield
        return

    ctx = extract_context(headers)
    span = None
    try:
        span = tracer.start_span(
            "model.execute",
            context=ctx,
            kind=trace.SpanKind.INTERNAL,
        )
    except Exception:
        logger.warning("Failed to start model span", exc_info=True)

    if span is None:
        yield
        return

    try:
        yield
        span.set_status(StatusCode.OK)
    except Exception as exc:
        try:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
        except Exception:
            logger.warning("Failed to record span error", exc_info=True)
        raise
    finally:
        try:
            span.end()
        except Exception:
            logger.warning("Failed to end model span", exc_info=True)


def init_tracer(tracer: Any = None) -> None:  # noqa: ANN401
    global _tracer, _initialized
    _tracer = tracer
    _initialized = True


def reset() -> None:
    global _tracer, _initialized
    _tracer = None
    _initialized = False
