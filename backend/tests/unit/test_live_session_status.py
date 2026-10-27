from datetime import UTC, datetime, timedelta

import pytest
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionStatus,
    LiveSessionVisibility,
)
from luml.settings import config

from tests.support.ids import LIVE_SESSION_ID, ORBIT_ID, OTHER_USER_ID, USER_ID


def make_session(
    *,
    started_ago: timedelta = timedelta(hours=2),
    heartbeat_ago: timedelta | None = None,
    connected: bool = True,
    ended_ago: timedelta | None = None,
    viewer_activity_ago: timedelta | None = None,
) -> LiveSession:
    now = datetime.now(UTC)
    return LiveSession(
        id=LIVE_SESSION_ID,
        orbit_id=ORBIT_ID,
        user_id=USER_ID,
        label="training run",
        visibility=LiveSessionVisibility.OWNER,
        started_at=now - started_ago,
        last_heartbeat_at=None if heartbeat_ago is None else now - heartbeat_ago,
        connected=connected,
        ended_at=None if ended_ago is None else now - ended_ago,
        last_viewer_activity_at=(
            None if viewer_activity_ago is None else now - viewer_activity_ago
        ),
    )


class TestLiveSessionStatus:
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
        self, heartbeat_ago: timedelta, connected: bool, expected: LiveSessionStatus
    ) -> None:
        session = make_session(heartbeat_ago=heartbeat_ago, connected=connected)

        assert session.status == expected

    def test_ended_session_is_ended_despite_recent_heartbeat(self) -> None:
        session = make_session(
            heartbeat_ago=timedelta(seconds=5), ended_ago=timedelta(seconds=1)
        )

        assert session.status == LiveSessionStatus.ENDED

    def test_new_session_without_heartbeat_is_disconnected(self) -> None:
        session = make_session(started_ago=timedelta(seconds=1), connected=False)

        assert session.status == LiveSessionStatus.DISCONNECTED

    def test_session_silent_since_start_for_an_hour_is_ended(self) -> None:
        session = make_session(started_ago=timedelta(minutes=61), connected=False)

        assert session.status == LiveSessionStatus.ENDED

    def test_session_nobody_viewed_since_start_for_the_idle_period_is_ended(
        self,
    ) -> None:
        session = make_session(
            started_ago=timedelta(days=7, minutes=1),
            heartbeat_ago=timedelta(seconds=10),
        )

        assert session.status == LiveSessionStatus.ENDED
        assert session.implied_end == session.started_at + timedelta(days=7)

    def test_session_without_viewer_activity_is_live_within_the_idle_period(
        self,
    ) -> None:
        session = make_session(
            started_ago=timedelta(days=6, hours=23),
            heartbeat_ago=timedelta(seconds=10),
        )

        assert session.status == LiveSessionStatus.LIVE

    def test_viewer_activity_resets_the_idle_clock(self) -> None:
        session = make_session(
            started_ago=timedelta(days=8),
            heartbeat_ago=timedelta(seconds=10),
            viewer_activity_ago=timedelta(days=1),
        )

        assert session.status == LiveSessionStatus.LIVE

    def test_viewer_activity_older_than_the_idle_period_ends_the_session(
        self,
    ) -> None:
        session = make_session(
            started_ago=timedelta(days=20),
            heartbeat_ago=timedelta(seconds=10),
            viewer_activity_ago=timedelta(days=8),
        )

        assert session.status == LiveSessionStatus.ENDED
        assert session.last_viewer_activity_at is not None
        assert session.implied_end == session.last_viewer_activity_at + timedelta(
            days=7
        )

    def test_idle_period_follows_the_setting(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config, "LIVE_SESSION_VIEWER_IDLE_SECONDS", 60)
        session = make_session(
            started_ago=timedelta(minutes=5),
            heartbeat_ago=timedelta(seconds=10),
            viewer_activity_ago=timedelta(minutes=2),
        )

        assert session.status == LiveSessionStatus.ENDED

    def test_status_is_serialized(self) -> None:
        dumped = make_session(heartbeat_ago=timedelta(seconds=10)).model_dump(
            mode="json"
        )

        assert dumped["status"] == "live"
        assert dumped["visibility"] == "owner"
        assert dumped["label"] == "training run"
        assert "implied_end" not in dumped

    def test_owner_visibility_shows_the_session_to_its_starter_only(self) -> None:
        session = make_session()

        assert session.is_visible_to(USER_ID)
        assert not session.is_visible_to(OTHER_USER_ID)

    def test_only_the_starter_may_end_a_session(self) -> None:
        session = make_session()

        assert session.may_be_ended_by(USER_ID)
        assert not session.may_be_ended_by(OTHER_USER_ID)

    def test_another_visibility_value_is_refused(self) -> None:
        with pytest.raises(ValueError, match="visibility"):
            LiveSession.model_validate(
                {**make_session().model_dump(), "visibility": "orbit"}
            )
