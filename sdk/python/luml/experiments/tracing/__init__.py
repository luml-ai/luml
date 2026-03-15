from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from luml.experiments.tracker import ExperimentTracker

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider


class TracerManager:
    _log_fn: Callable | None = None
    _provider: TracerProvider | None = None

    @classmethod
    def setup_luml_tracing(
        cls,
    ) -> None:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from luml.experiments.tracing.span_exporter import LumlSpanExporter

        service_name: str = "luml-sdk"
        resource_attrs = {"service.name": service_name}

        resource = Resource.create(resource_attrs)

        tracer_provider = TracerProvider(resource=resource)

        exporter = LumlSpanExporter(
            log_fn=cls._logger,
        )

        span_processor = BatchSpanProcessor(span_exporter=exporter)

        tracer_provider.add_span_processor(span_processor)

        trace.set_tracer_provider(tracer_provider)
        cls._provider = tracer_provider

    @classmethod
    def _logger(cls, *args, **kwargs) -> None:
        if cls._log_fn:
            cls._log_fn(*args, **kwargs)
        else:
            raise ValueError("Log function is not set. Call setup_luml_tracing first.")

    @classmethod
    def flush(cls, timeout_millis: int = 30000) -> bool:
        if cls._provider is None:
            return True
        return cls._provider.force_flush(timeout_millis)

    @classmethod
    def set_experiment_tracker(cls, tracker: ExperimentTracker) -> None:
        if not isinstance(tracker, ExperimentTracker):
            raise ValueError("tracker must be an instance of ExperimentTracker")
        cls._log_fn = tracker.log_span
        tracker.add_pre_end_hook(cls.flush)


setup_tracing = TracerManager.setup_luml_tracing
set_experiment_tracker = TracerManager.set_experiment_tracker
flush_tracing = TracerManager.flush


def instrument_openai() -> None:
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor

    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument()
