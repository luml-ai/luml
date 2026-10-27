from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.exceptions import LiveSessionEndedError
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionHeartbeatIn,
    LiveSessionStatus,
    LiveSessionViewTokenIn,
    SessionTokenKind,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import RelayStatus

from tests.support.ids import (
    LIVE_SESSION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_RELAY_ID,
    RELAY_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.live_sessions.conftest import (
    _assert_lifetime,
    _issued,
    _orbit,
    _relay,
    _session,
)


class TestLiveSessionTokens:
    async def test_heartbeat_renews_a_token_about_to_expire(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.get_live_session.return_value = _session()
        mocks.repo.record_heartbeat.return_value = _session()

        result = await mocks.handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionHeartbeatIn(
                connected=True,
                token_expires_at=datetime.now(UTC) + timedelta(minutes=2),
            ),
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.UPDATE, ORBIT_ID
        )
        mocks.repo.record_heartbeat.assert_awaited_once_with(LIVE_SESSION_ID, True)
        assert result.status == LiveSessionStatus.LIVE
        [issued] = _issued(mocks)
        assert (issued.kind, issued.session_id) == (
            SessionTokenKind.EXPOSE,
            LIVE_SESSION_ID,
        )
        _assert_lifetime(issued, 600)
        assert result.expose_token == "opaque-0"
        assert result.token_expires_at == issued.expires_at

    async def test_heartbeat_well_before_expiry_carries_no_token(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.get_live_session.return_value = _session()
        mocks.repo.record_heartbeat.return_value = _session(connected=False)

        result = await mocks.handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionHeartbeatIn(
                connected=False,
                token_expires_at=datetime.now(UTC) + timedelta(minutes=9),
            ),
        )

        mocks.repo.record_heartbeat.assert_awaited_once_with(LIVE_SESSION_ID, False)
        assert result.status == LiveSessionStatus.DISCONNECTED
        assert result.expose_token is None
        assert result.token_expires_at is None
        mocks.token_repo.issue_token.assert_not_awaited()

    @pytest.mark.parametrize(
        "stored",
        [
            _session(ended_at=datetime.now(UTC) - timedelta(minutes=1)),
            _session(last_heartbeat_ago=timedelta(hours=1, minutes=1)),
            _session(started_ago=timedelta(days=8)),
        ],
        ids=["ended", "silent-for-an-hour", "no-viewer-for-the-idle-period"],
    )
    async def test_heartbeat_to_an_ended_session_says_so_and_carries_no_token(
        self, mocks: CollaboratorMocks[LiveSessionHandler], stored: LiveSession
    ) -> None:
        mocks.repo.get_live_session.return_value = stored
        mocks.repo.record_heartbeat.return_value = stored

        result = await mocks.handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionHeartbeatIn(connected=True, token_expires_at=datetime.now(UTC)),
        )

        assert result.status == LiveSessionStatus.ENDED
        assert result.expose_token is None
        mocks.token_repo.issue_token.assert_not_awaited()

    @pytest.mark.parametrize(
        "stored",
        [_session(ended_at=datetime.now(UTC)), _session(started_ago=timedelta(days=8))],
        ids=["ended", "no-viewer-for-the-idle-period"],
    )
    async def test_view_token_is_refused_for_an_ended_session(
        self, mocks: CollaboratorMocks[LiveSessionHandler], stored: LiveSession
    ) -> None:
        mocks.repo.get_live_session.return_value = stored

        with pytest.raises(LiveSessionEndedError):
            await mocks.handler.issue_view_token(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
            )

        mocks.token_repo.issue_token.assert_not_awaited()
        mocks.repo.record_viewer_activity.assert_not_awaited()

    @pytest.mark.parametrize("connected", [True, False], ids=["live", "disconnected"])
    async def test_view_token_fits_one_viewer_and_one_session(
        self, mocks: CollaboratorMocks[LiveSessionHandler], connected: bool
    ) -> None:
        mocks.repo.get_live_session.return_value = _session(connected=connected)

        result = await mocks.handler.issue_view_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.READ, ORBIT_ID
        )
        mocks.relay_repo.get_relay.assert_awaited_once_with(RELAY_ID)
        [issued] = _issued(mocks)
        assert (
            issued.kind,
            issued.session_id,
            issued.user_id,
            issued.destination,
        ) == (SessionTokenKind.VIEW, LIVE_SESSION_ID, USER_ID, None)
        _assert_lifetime(issued, 300)
        assert (result.token, result.expires_at) == ("opaque-0", issued.expires_at)
        mocks.repo.record_viewer_activity.assert_awaited_once_with(LIVE_SESSION_ID)
        launch = urlsplit(result.launch_url)
        assert f"{launch.scheme}://{launch.netloc}{launch.path}" == (
            "https://k3f9x2ab.sessions.example/.luml-relay/launch"
        )
        assert parse_qs(launch.query) == {"token": [result.token]}

    async def test_view_token_stores_the_destination_outside_the_launch_address(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.get_live_session.return_value = _session()

        result = await mocks.handler.issue_view_token(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionViewTokenIn(destination="/experiments/42?tab=metrics"),
        )

        [issued] = _issued(mocks)
        assert issued.destination == "/experiments/42?tab=metrics"
        launch = urlsplit(result.launch_url)
        assert launch.path == "/.luml-relay/launch"
        assert parse_qs(launch.query) == {"token": [result.token]}

    async def test_a_session_keeps_its_relay_when_the_orbit_is_reassigned(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.orbit_repo.get_orbit_simple.return_value = _orbit(relay_id=OTHER_RELAY_ID)
        mocks.repo.get_live_session.return_value = _session()
        mocks.repo.record_heartbeat.return_value = _session()

        heartbeat = await mocks.handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionHeartbeatIn(
                connected=True,
                token_expires_at=datetime.now(UTC) + timedelta(minutes=1),
            ),
        )
        view = await mocks.handler.issue_view_token(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
        )

        assert heartbeat.expose_token is not None
        assert [issued.session_id for issued in _issued(mocks)] == [LIVE_SESSION_ID] * 2
        assert view.launch_url.startswith("https://k3f9x2ab.sessions.example/")
        mocks.relay_repo.get_relay.assert_awaited_once_with(RELAY_ID)
        mocks.orbit_repo.get_orbit_simple.assert_not_awaited()

    async def test_a_draining_relay_keeps_renewing_its_sessions(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay(status=RelayStatus.DRAINING)
        mocks.repo.get_live_session.return_value = _session()
        mocks.repo.record_heartbeat.return_value = _session()

        result = await mocks.handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionHeartbeatIn(
                connected=True,
                token_expires_at=datetime.now(UTC) + timedelta(minutes=1),
            ),
        )

        assert result.status == LiveSessionStatus.LIVE
        assert result.expose_token is not None

    async def test_a_session_whose_relay_was_removed_gets_no_credentials(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        ended = _session(ended_at=datetime.now(UTC), relay_id=None)
        mocks.repo.get_live_session.return_value = ended
        mocks.repo.record_heartbeat.return_value = ended

        heartbeat = await mocks.handler.record_heartbeat(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LIVE_SESSION_ID,
            LiveSessionHeartbeatIn(connected=True, token_expires_at=datetime.now(UTC)),
        )
        with pytest.raises(LiveSessionEndedError):
            await mocks.handler.issue_view_token(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
            )

        assert heartbeat.status == LiveSessionStatus.ENDED
        assert heartbeat.expose_token is None
        mocks.token_repo.issue_token.assert_not_awaited()
