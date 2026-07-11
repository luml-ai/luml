import json
import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import MeterProvider, NoOpMeterProvider
from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import NoOpTracerProvider, TracerProvider

from agent.monitoring.events import InferenceEvent
from agent.monitoring.metrics import InferenceMetrics

logger = logging.getLogger(__name__)

_SERVICE_NAME = "satellite-agent"


class _NoOpEventExporter:
    def emit(self, event: InferenceEvent) -> None:
        pass

    def shutdown(self) -> None:
        pass


class _OTLPEventExporter:
    def __init__(self, span_exporter: SpanExporter) -> None:
        self._provider = SDKTracerProvider(
            resource=Resource.create({"service.name": f"{_SERVICE_NAME}.events"}),
        )
        self._provider.add_span_processor(BatchSpanProcessor(span_exporter))
        self._tracer = self._provider.get_tracer("inference.events")

    def emit(self, event: InferenceEvent) -> None:
        with self._tracer.start_as_current_span("inference_event") as span:
            for key, value in event.to_dict().items():
                if value is not None:
                    if isinstance(value, dict):
                        span.set_attribute(f"inference.{key}", json.dumps(value))
                    elif isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"inference.{key}", value)

    def shutdown(self) -> None:
        self._provider.shutdown()


class TelemetrySetup:
    def __init__(
        self,
        *,
        endpoint: str | None = None,
        enabled: bool = True,
        tracer_provider: TracerProvider | None = None,
        meter_provider: MeterProvider | None = None,
        event_exporter: _NoOpEventExporter | _OTLPEventExporter | None = None,
        span_exporter: SpanExporter | None = None,
        metric_exporter: MetricExporter | None = None,
    ) -> None:
        self._active = False
        self._owns_providers = False

        if tracer_provider or meter_provider or event_exporter:
            self._tracer_provider: TracerProvider = tracer_provider or NoOpTracerProvider()
            self._meter_provider: MeterProvider = meter_provider or NoOpMeterProvider()
            self._event_exporter: _NoOpEventExporter | _OTLPEventExporter = (
                event_exporter or _NoOpEventExporter()
            )
            self._active = bool(enabled and endpoint)
            return

        if not enabled or not endpoint:
            self._tracer_provider = NoOpTracerProvider()
            self._meter_provider = NoOpMeterProvider()
            self._event_exporter = _NoOpEventExporter()
            return

        try:
            resource = Resource.create({"service.name": _SERVICE_NAME})
            _span_exporter = span_exporter or OTLPSpanExporter(endpoint=endpoint, insecure=True)
            _metric_exporter = metric_exporter or OTLPMetricExporter(
                endpoint=endpoint, insecure=True
            )

            tp = SDKTracerProvider(resource=resource)
            tp.add_span_processor(BatchSpanProcessor(_span_exporter))
            self._tracer_provider = tp

            reader = PeriodicExportingMetricReader(_metric_exporter)
            self._meter_provider = SDKMeterProvider(resource=resource, metric_readers=[reader])

            event_span_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            self._event_exporter = _OTLPEventExporter(event_span_exporter)

            self._active = True
            self._owns_providers = True
        except Exception:
            logger.warning("Failed to initialize telemetry; falling back to no-op", exc_info=True)
            self._tracer_provider = NoOpTracerProvider()
            self._meter_provider = NoOpMeterProvider()
            self._event_exporter = _NoOpEventExporter()

    @property
    def active(self) -> bool:
        return self._active

    def tracer(self, name: str = _SERVICE_NAME) -> trace.Tracer:
        return self._tracer_provider.get_tracer(name)

    def meter(self, name: str = _SERVICE_NAME) -> metrics.Meter:
        return self._meter_provider.get_meter(name)

    def inference_metrics(self) -> InferenceMetrics:
        return InferenceMetrics(self.meter())

    def emit_event(self, event: InferenceEvent) -> None:
        try:
            self._event_exporter.emit(event)
        except Exception:
            logger.warning("Failed to emit inference event", exc_info=True)

    def shutdown(self) -> None:
        if self._owns_providers:
            if isinstance(self._tracer_provider, SDKTracerProvider):
                self._tracer_provider.shutdown()
            if isinstance(self._meter_provider, SDKMeterProvider):
                self._meter_provider.shutdown()
        self._event_exporter.shutdown()

    def __repr__(self) -> str:
        return f"TelemetrySetup(active={self._active})"


def create_telemetry(
    *,
    endpoint: str | None = None,
    enabled: bool = True,
) -> TelemetrySetup:
    return TelemetrySetup(endpoint=endpoint, enabled=enabled)
