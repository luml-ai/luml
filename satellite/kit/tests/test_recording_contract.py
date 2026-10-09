import pytest

from luml_satellite.workload import InferenceOutcome, NoOpRecorder, RecordingPolicy


def test_recording_policy_selects_bodies_at_the_boundary() -> None:
    policy = RecordingPolicy(
        sample_rate=0.25,
        body_max_bytes=1024,
        keep_inputs=True,
        keep_outputs=False,
    )

    assert policy.captures_bodies(0.2499)
    assert not policy.captures_bodies(0.25)
    assert not RecordingPolicy(keep_inputs=False, keep_outputs=False).captures_bodies(0)


def test_recording_policy_validates_configuration() -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        RecordingPolicy(sample_rate=1.1)
    with pytest.raises(ValueError, match="body_max_bytes"):
        RecordingPolicy(body_max_bytes=0)
    with pytest.raises(ValueError, match="random_value"):
        RecordingPolicy().captures_bodies(1)


@pytest.mark.asyncio
async def test_no_op_recorder_never_creates_an_event_or_headers() -> None:
    session = await NoOpRecorder().start("deployment", {"safe": "input"}, RecordingPolicy())

    assert session.event_id is None
    assert session.upstream_headers == {}
    await session.complete(InferenceOutcome(status_code=200, latency_ms=1.5))
