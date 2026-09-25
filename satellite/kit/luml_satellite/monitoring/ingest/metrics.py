from opentelemetry.metrics import Counter, Histogram, Meter


class InferenceMetrics:
    def __init__(self, meter: Meter) -> None:
        self.request_counter: Counter = meter.create_counter(
            name="inference.requests",
            description="Total inference requests",
        )
        self.error_counter: Counter = meter.create_counter(
            name="inference.errors",
            description="Total inference errors",
        )
        self.latency_histogram: Histogram = meter.create_histogram(
            name="inference.latency_ms",
            description="Inference latency in milliseconds",
            unit="ms",
        )
