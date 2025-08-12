from collections.abc import Callable

from dataforce.experiments.tracker import ExperimentTracker


class TracerManager:
    _log_fn: Callable | None = None

    @classmethod
    def setup_dataforce_tracing(
        cls,
    ) -> None:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        from dataforce.experiments.tracing.span_exporter import DataforceSpanExporter

        service_name: str = "dataforce-sdk"
        resource_attrs = {"service.name": service_name}

        resource = Resource.create(resource_attrs)

        tracer_provider = TracerProvider(resource=resource)

        exporter = DataforceSpanExporter(
            log_fn=cls._logger,
        )

        span_processor = SimpleSpanProcessor(span_exporter=exporter)

        tracer_provider.add_span_processor(span_processor)

        trace.set_tracer_provider(tracer_provider)

    @classmethod
    def _logger(cls, *args, **kwargs) -> None:
        if cls._log_fn:
            cls._log_fn(*args, **kwargs)
        else:
            raise ValueError(
                "Log function is not set. Call setup_dataforce_tracing first."
            )

    @classmethod
    def set_experiment_tracker(cls, tracker: ExperimentTracker) -> None:
        if not isinstance(tracker, ExperimentTracker):
            raise ValueError("tracker must be an instance of ExperimentTracker")
        cls._log_fn = tracker.log_span


setup_tracing = TracerManager.setup_dataforce_tracing
set_experiment_tracker = TracerManager.set_experiment_tracker


def instrument_openai() -> None:
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor

    instrumentor = OpenAIInstrumentor()
    instrumentor.instrument()
