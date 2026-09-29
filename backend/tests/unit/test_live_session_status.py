from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from luml.schemas.live_session import LiveSession, LiveSessionStatus

ORBIT_ID = UUID("0199c337-0a02-753e-9def-b27745e69be6")
USER_ID = UUID("0199c337-0a00-7d8f-b0c4-b68349bbe24b")


def make_session(
    *,
    started_ago: timedelta = timedelta(hours=2),
    heartbeat_ago: timedelta | None = None,
    connected: bool = True,
    ended_ago: timedelta | None = None,
) -> LiveSession:
    now = datetime.now(UTC)
    return LiveSession(
        id="k3f9x2ab",
        orbit_id=ORBIT_ID,
        user_id=USER_ID,
        name="training run",
        relay_id="default",
        started_at=now - started_ago,
        last_heartbeat_at=None if heartbeat_ago is None else now - heartbeat_ago,
        connected=connected,
        ended_at=None if ended_ago is None else now - ended_ago,
    )


@pytest.mark.parametrize(
    ("heartbeat_ago", "connected", "expected"),
    [
        (timedelta(seconds=10), True, LiveSessionStatus.LIVE),
        (timedelta(seconds=10), False, LiveSessionStatus.DISCONNECTED),
        (timedelta(seconds=100), True, LiveSessionStatus.DISCONNECTED),
        (timedelta(minutes=61), True, LiveSessionStatus.ENDED),
        (timedelta(minutes=61), False, LiveSessionStatus.ENDED),
    ],
)
def test_status_follows_heartbeats(
    heartbeat_ago: timedelta, connected: bool, expected: LiveSessionStatus
) -> None:
    session = make_session(heartbeat_ago=heartbeat_ago, connected=connected)

    assert session.status == expected


def test_ended_session_is_ended_despite_recent_heartbeat() -> None:
    session = make_session(
        heartbeat_ago=timedelta(seconds=5), ended_ago=timedelta(seconds=1)
    )

    assert session.status == LiveSessionStatus.ENDED


def test_new_session_without_heartbeat_is_disconnected() -> None:
    session = make_session(started_ago=timedelta(seconds=1), connected=False)

    assert session.status == LiveSessionStatus.DISCONNECTED


def test_session_silent_since_start_for_an_hour_is_ended() -> None:
    session = make_session(started_ago=timedelta(minutes=61), connected=False)

    assert session.status == LiveSessionStatus.ENDED


def test_status_is_serialized() -> None:
    dumped = make_session(heartbeat_ago=timedelta(seconds=10)).model_dump(mode="json")

    assert dumped["status"] == "live"
