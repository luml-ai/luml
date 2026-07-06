import sys
from pathlib import Path

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from agent.monitoring.testing import InMemorySpanExporter

# model_server code imports via bare module names (e.g. `from telemetry import ...`)
# because conda_worker.py runs with model_server/ on sys.path.
_model_server_dir = str(Path(__file__).resolve().parent.parent / "model_server")
if _model_server_dir not in sys.path:
    sys.path.insert(0, _model_server_dir)

from model_server.telemetry import (  # noqa: E402
    extract_context,
    init_tracer,
    model_span,
    reset,
)


@pytest.fixture(autouse=True)
def _reset_tracer() -> None:
    reset()
    yield  # type: ignore[misc]
    reset()


def _make_tracer(exporter: InMemorySpanExporter) -> object:
    resource = Resource.create({"service.name": "test-model-server"})
    provider = SDKTracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test")


class TestModelSpanCreated:
    async def test_span_created_with_traceparent(self) -> None:
        exporter = InMemorySpanExporter()
        tracer = _make_tracer(exporter)
        init_tracer(tracer)

        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        async with model_span({"traceparent": traceparent}):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "model.execute"
        assert span.status.is_ok

    async def test_span_continues_parent_trace(self) -> None:
        exporter = InMemorySpanExporter()
        tracer = _make_tracer(exporter)
        init_tracer(tracer)

        trace_id = "0af7651916cd43dd8448eb211c80319c"
        parent_span_id = "b7ad6b7169203331"
        traceparent = f"00-{trace_id}-{parent_span_id}-01"

        async with model_span({"traceparent": traceparent}):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        actual_trace_id = format(span.context.trace_id, "032x")
        assert actual_trace_id == trace_id
        assert span.parent is not None
        actual_parent_span_id = format(span.parent.span_id, "016x")
        assert actual_parent_span_id == parent_span_id

    async def test_span_without_traceparent(self) -> None:
        exporter = InMemorySpanExporter()
        tracer = _make_tracer(exporter)
        init_tracer(tracer)

        async with model_span({}):
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].parent is None


class TestNoTelemetry:
    async def test_no_span_when_tracer_is_none(self) -> None:
        init_tracer(None)

        async with model_span({"traceparent": "00-abc-def-01"}):
            pass
        # no error, no span — just a passthrough

    async def test_execution_unaffected_when_telemetry_off(self) -> None:
        init_tracer(None)
        result = None

        async with model_span({}):
            result = 42

        assert result == 42


class TestBestEffort:
    async def test_model_error_still_raised(self) -> None:
        exporter = InMemorySpanExporter()
        tracer = _make_tracer(exporter)
        init_tracer(tracer)

        with pytest.raises(ValueError, match="model failed"):
            async with model_span({}):
                raise ValueError("model failed")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert not spans[0].status.is_ok

    async def test_model_error_raised_without_tracer(self) -> None:
        init_tracer(None)

        with pytest.raises(RuntimeError, match="boom"):
            async with model_span({}):
                raise RuntimeError("boom")


class TestExtractContext:
    def test_extracts_valid_traceparent(self) -> None:
        headers = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
        ctx = extract_context(headers)
        assert ctx is not None

    def test_returns_context_for_empty_headers(self) -> None:
        ctx = extract_context({})
        assert ctx is not None


class TestBaseServiceHeaders:
    async def test_post_handler_receives_headers(self) -> None:
        from services.base_service import UvicornBaseService

        app = UvicornBaseService()
        captured: dict[str, str] = {}

        @app.post("/test")
        async def handler(*, headers: dict[str, str], request_data: dict) -> dict:
            captured.update(headers)
            return {"ok": True}

        send_calls: list[dict] = []

        async def mock_receive() -> dict:
            return {"type": "http.request", "body": b'{"key": "val"}', "more_body": False}

        async def mock_send(msg: dict) -> None:
            send_calls.append(msg)

        scope = {
            "type": "http",
            "path": "/test",
            "method": "POST",
            "headers": [
                (b"traceparent", b"00-abc123-def456-01"),
                (b"content-type", b"application/json"),
            ],
        }

        await app(scope, mock_receive, mock_send)

        assert captured["traceparent"] == "00-abc123-def456-01"
        assert captured["content-type"] == "application/json"
