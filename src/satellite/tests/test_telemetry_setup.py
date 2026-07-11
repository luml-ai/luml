from agent.monitoring import InferenceEvent, create_telemetry
from agent.monitoring.testing import FakeTelemetry


class TestTelemetryNoOp:
    def test_noop_when_endpoint_missing(self) -> None:
        setup = create_telemetry(endpoint=None, enabled=True)
        assert not setup.active

    def test_noop_when_disabled(self) -> None:
        setup = create_telemetry(endpoint="http://localhost:4317", enabled=False)
        assert not setup.active

    def test_noop_when_both_missing_and_disabled(self) -> None:
        setup = create_telemetry(endpoint=None, enabled=False)
        assert not setup.active

    def test_noop_emit_event_does_not_raise(self) -> None:
        setup = create_telemetry(endpoint=None)
        event = InferenceEvent(
            event_id="test",
            deployment_id="dep-1",
            status="success",
            latency_ms=10.0,
        )
        setup.emit_event(event)

    def test_noop_tracer_returns_tracer(self) -> None:
        setup = create_telemetry(endpoint=None)
        tracer = setup.tracer()
        assert tracer is not None

    def test_noop_meter_returns_meter(self) -> None:
        setup = create_telemetry(endpoint=None)
        meter = setup.meter()
        assert meter is not None

    def test_noop_shutdown_does_not_raise(self) -> None:
        setup = create_telemetry(endpoint=None)
        setup.shutdown()

    def test_noop_inference_metrics_does_not_raise(self) -> None:
        setup = create_telemetry(endpoint=None)
        m = setup.inference_metrics()
        m.request_counter.add(1, {"deployment_id": "d", "status": "success"})
        m.error_counter.add(1, {"deployment_id": "d", "status_code": "500"})
        m.latency_histogram.record(42.0, {"deployment_id": "d", "status": "success"})


class TestTelemetryActive:
    def test_active_with_fake_telemetry(self, fake_telemetry: FakeTelemetry) -> None:
        assert fake_telemetry.setup.active

    def test_emit_event_captured(self, fake_telemetry: FakeTelemetry) -> None:
        event = InferenceEvent(
            event_id="evt-1",
            deployment_id="dep-1",
            status="success",
            latency_ms=15.5,
            inputs={"feature": 1.0},
            output={"prediction": 42},
        )
        fake_telemetry.setup.emit_event(event)
        assert len(fake_telemetry.events) == 1
        assert fake_telemetry.events[0].event_id == "evt-1"
        assert fake_telemetry.events[0].status == "success"

    def test_tracer_creates_spans(self, fake_telemetry: FakeTelemetry) -> None:
        tracer = fake_telemetry.setup.tracer()
        with tracer.start_as_current_span("test-span"):
            pass
        spans = fake_telemetry.spans
        assert len(spans) == 1
        assert spans[0].name == "test-span"

    def test_metrics_recorded(self, fake_telemetry: FakeTelemetry) -> None:
        m = fake_telemetry.setup.inference_metrics()
        m.request_counter.add(1, {"deployment_id": "dep-1", "status": "success"})
        m.latency_histogram.record(25.0, {"deployment_id": "dep-1", "status": "success"})

        metrics_data = fake_telemetry.get_metrics()
        assert "inference.requests" in metrics_data
        assert "inference.latency_ms" in metrics_data

    def test_error_counter_recorded(self, fake_telemetry: FakeTelemetry) -> None:
        m = fake_telemetry.setup.inference_metrics()
        m.error_counter.add(1, {"deployment_id": "dep-1", "status_code": "500"})

        metrics_data = fake_telemetry.get_metrics()
        assert "inference.errors" in metrics_data

    def test_multiple_events_captured(self, fake_telemetry: FakeTelemetry) -> None:
        for i in range(3):
            event = InferenceEvent(
                event_id=f"evt-{i}",
                deployment_id="dep-1",
                status="success",
                latency_ms=10.0 + i,
            )
            fake_telemetry.setup.emit_event(event)
        assert len(fake_telemetry.events) == 3


class TestTelemetrySetupRepr:
    def test_repr_active(self, fake_telemetry: FakeTelemetry) -> None:
        assert "active=True" in repr(fake_telemetry.setup)

    def test_repr_noop(self) -> None:
        setup = create_telemetry(endpoint=None)
        assert "active=False" in repr(setup)


class TestInferenceEvent:
    def test_to_dict_success(self) -> None:
        event = InferenceEvent(
            event_id="evt-1",
            deployment_id="dep-1",
            status="success",
            latency_ms=12.5,
            inputs={"a": 1},
            output={"b": 2},
            trace_id="abc",
            span_id="def",
        )
        d = event.to_dict()
        assert d["event_id"] == "evt-1"
        assert d["deployment_id"] == "dep-1"
        assert d["status"] == "success"
        assert d["latency_ms"] == 12.5
        assert d["inputs"] == {"a": 1}
        assert d["output"] == {"b": 2}
        assert d["trace_id"] == "abc"
        assert d["span_id"] == "def"
        assert "timestamp" in d
        assert "status_code" not in d
        assert "error" not in d

    def test_to_dict_error(self) -> None:
        event = InferenceEvent(
            event_id="evt-2",
            deployment_id="dep-1",
            status="error",
            latency_ms=5.0,
            status_code=500,
            error="model crashed",
        )
        d = event.to_dict()
        assert d["status"] == "error"
        assert d["status_code"] == 500
        assert d["error"] == "model crashed"
        assert "inputs" not in d
        assert "output" not in d

    def test_to_dict_minimal(self) -> None:
        event = InferenceEvent(
            event_id="evt-3",
            deployment_id="dep-1",
            status="success",
            latency_ms=1.0,
        )
        d = event.to_dict()
        assert set(d.keys()) == {"event_id", "deployment_id", "status", "latency_ms", "timestamp"}
