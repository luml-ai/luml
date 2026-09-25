from collections import deque

from luml_satellite.monitoring import InferenceInstrumentation
from luml_satellite.monitoring.ingest.testing import FakeTelemetry
from luml_satellite.workload import InferenceOutcome, RecordingPolicy


async def test_instrumentation_records_every_call_and_samples_only_selected_bodies(
    fake_telemetry: FakeTelemetry,
) -> None:
    draws = deque([0.75, 0.25])
    recorder = InferenceInstrumentation(fake_telemetry.setup, random_source=draws.popleft)
    policy = RecordingPolicy(sample_rate=0.5, body_max_bytes=1024)

    missed = await recorder.start("deployment", {"safe": "first"}, policy)
    await missed.complete(InferenceOutcome(status_code=200, latency_ms=12.5, output={"ok": 1}))
    sampled = await recorder.start("deployment", {"safe": "second"}, policy)
    await sampled.complete(
        InferenceOutcome(status_code=201, latency_ms=8.0, output={"prediction": 42})
    )

    assert len(fake_telemetry.events) == 2
    assert fake_telemetry.events[0].bodies_sampled is False
    assert fake_telemetry.events[0].inputs is None
    assert fake_telemetry.events[0].output is None
    assert fake_telemetry.events[1].bodies_sampled is True
    assert fake_telemetry.events[1].inputs == {"safe": "second"}
    assert fake_telemetry.events[1].output == {"prediction": 42}
    assert fake_telemetry.events[1].status_code == 201
    assert sampled.event_id is not None
    assert "traceparent" in sampled.upstream_headers


async def test_instrumentation_applies_body_cap_and_keep_flags(
    fake_telemetry: FakeTelemetry,
) -> None:
    recorder = InferenceInstrumentation(fake_telemetry.setup, random_source=lambda: 0.0)

    too_large = await recorder.start(
        "deployment",
        {"value": "x" * 100},
        RecordingPolicy(body_max_bytes=50),
    )
    await too_large.complete(
        InferenceOutcome(status_code=200, latency_ms=1.0, output={"small": True})
    )
    outputs_only = await recorder.start(
        "deployment",
        {"value": "small"},
        RecordingPolicy(keep_inputs=False, keep_outputs=True),
    )
    await outputs_only.complete(
        InferenceOutcome(status_code=200, latency_ms=2.0, output={"kept": True})
    )

    assert fake_telemetry.events[0].bodies_sampled is False
    assert fake_telemetry.events[0].inputs is None
    assert fake_telemetry.events[0].output is None
    assert fake_telemetry.events[1].bodies_sampled is True
    assert fake_telemetry.events[1].inputs is None
    assert fake_telemetry.events[1].output == {"kept": True}


async def test_instrumentation_records_failed_outcome_and_completes_once(
    fake_telemetry: FakeTelemetry,
) -> None:
    recorder = InferenceInstrumentation(fake_telemetry.setup, random_source=lambda: 0.0)
    session = await recorder.start("deployment", {"safe": True}, RecordingPolicy())
    outcome = InferenceOutcome(
        status_code=504,
        latency_ms=45_000.0,
        error="upstream timeout",
    )

    await session.complete(outcome)
    await session.complete(outcome)

    assert len(fake_telemetry.events) == 1
    event = fake_telemetry.events[0]
    assert event.status == "error"
    assert event.status_code == 504
    assert event.latency_ms == 45_000.0
    assert event.error == "upstream timeout"
