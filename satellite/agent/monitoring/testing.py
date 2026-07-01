import threading
from collections.abc import Sequence
from typing import Any

from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import (
    ReadableSpan,
    TracerProvider as SDKTracerProvider,
)
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from agent.monitoring.events import InferenceEvent
from agent.monitoring.telemetry import TelemetrySetup


class InMemorySpanExporter(SpanExporter):
    def __init__(self) -> None:
        self._spans: list[ReadableSpan] = []
        self._lock = threading.Lock()

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> list[ReadableSpan]:
        with self._lock:
            return list(self._spans)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 0) -> bool:
        return True


class FakeEventExporter:
    def __init__(self) -> None:
        self.events: list[InferenceEvent] = []

    def emit(self, event: InferenceEvent) -> None:
        self.events.append(event)

    def shutdown(self) -> None:
        pass


class FakeTelemetry:
    def __init__(self) -> None:
        resource = Resource.create({"service.name": "test"})

        self.span_exporter = InMemorySpanExporter()
        tp = SDKTracerProvider(resource=resource)
        tp.add_span_processor(SimpleSpanProcessor(self.span_exporter))

        self.metric_reader = InMemoryMetricReader()
        mp = SDKMeterProvider(resource=resource, metric_readers=[self.metric_reader])

        self.event_exporter = FakeEventExporter()

        self.setup = TelemetrySetup(
            endpoint="http://fake:4317",
            enabled=True,
            tracer_provider=tp,
            meter_provider=mp,
            event_exporter=self.event_exporter,
        )

    @property
    def spans(self) -> list[Any]:
        return list(self.span_exporter.get_finished_spans())

    @property
    def events(self) -> list[InferenceEvent]:
        return self.event_exporter.events

    def get_metrics(self) -> dict[str, Any]:
        data = self.metric_reader.get_metrics_data()
        result: dict[str, Any] = {}
        if data and data.resource_metrics:
            for rm in data.resource_metrics:
                for sm in rm.scope_metrics:
                    for metric in sm.metrics:
                        result[metric.name] = metric
        return result

    def shutdown(self) -> None:
        self.setup.shutdown()
