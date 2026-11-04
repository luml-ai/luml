from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from luml.repositories.limits import OrganizationResource
from luml.schemas.live_session import (
    LiveSession,
    LiveSessionHeartbeatIn,
    LiveSessionStartIn,
    LiveSessionStatus,
    LiveSessionVisibility,
    SessionTokenKind,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import RelayStatus

from tests.support.ids import (
    LIVE_SESSION_ID,
    ORBIT_ID,
    ORGANIZATION_ID,
    OTHER_ORBIT_ID,
    OTHER_USER_ID,
    RELAY_ID,
    USER_ID,
)
from tests.support.mocks import CollaboratorMocks
from tests.unit.handlers.live_sessions.conftest import (
    AGENT_URL,
    _assert_lifetime,
    _issued,
    _orbit,
    _relay,
    _session,
)


class TestLiveSessions:
    async def test_start_session(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.create_live_session.return_value = _session(last_heartbeat_ago=None)

        result = await mocks.handler.start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="training run")
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.CREATE, ORBIT_ID
        )
        mocks.orbit_repo.get_orbit_simple.assert_awaited_once_with(
            ORBIT_ID, ORGANIZATION_ID
        )
        mocks.relay_repo.get_relay.assert_awaited_once_with(RELAY_ID)
        mocks.repo.check_session_slot.assert_awaited_once_with(
            ORGANIZATION_ID, OrganizationResource.OWN_RELAY_SESSIONS, None
        )
        assert mocks.repo.create_live_session.await_args is not None
        created, organization_id, limit, replacing = (
            mocks.repo.create_live_session.await_args.args
        )
        assert replacing is None
        assert (
            created.orbit_id,
            created.user_id,
            created.label,
            created.visibility,
            created.relay_id,
        ) == (ORBIT_ID, USER_ID, "training run", LiveSessionVisibility.OWNER, RELAY_ID)
        assert (organization_id, limit) == (
            ORGANIZATION_ID,
            OrganizationResource.OWN_RELAY_SESSIONS,
        )
        assert result.id == LIVE_SESSION_ID
        assert result.public_url == "https://k3f9x2ab.sessions.example"
        assert "app_url" not in result.model_dump()
        assert result.agent_url == AGENT_URL
        assert result.heartbeat_interval == 30
        [issued] = _issued(mocks)
        assert (issued.kind, issued.session_id, issued.user_id) == (
            SessionTokenKind.EXPOSE,
            LIVE_SESSION_ID,
            USER_ID,
        )
        _assert_lifetime(issued, 600)
        assert result.expose_token == "opaque-0"
        assert result.token_expires_at == issued.expires_at

    async def test_public_url_keeps_the_scheme_and_port_of_the_agent_address(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.create_live_session.return_value = _session(last_heartbeat_ago=None)
        mocks.relay_repo.get_relay.return_value = _relay(
            base_domain="sessions.localhost",
            agent_url="ws://sessions.localhost:8090/connect",
        )

        result = await mocks.handler.start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="dev")
        )

        assert result.public_url == "http://k3f9x2ab.sessions.localhost:8090"

    async def test_someone_outside_the_orbit_cannot_start_a_session(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.start_session(
                OTHER_USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                LiveSessionStartIn(label="run"),
            )

        mocks.repo.create_live_session.assert_not_awaited()

    async def test_list_asks_the_repository_for_the_callers_visible_sessions(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        own = _session()
        mocks.repo.list_live_sessions.return_value = [own]

        result = await mocks.handler.list_sessions(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        assert result == [own]
        mocks.repo.list_live_sessions.assert_awaited_once_with(ORBIT_ID, USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.LIST, ORBIT_ID
        )

    @pytest.mark.parametrize(
        "stored",
        [
            None,
            _session(user_id=OTHER_USER_ID),
            _session().model_copy(update={"orbit_id": OTHER_ORBIT_ID}),
        ],
        ids=["missing", "another-user", "another-orbit"],
    )
    @pytest.mark.parametrize("operation", ["get", "heartbeat", "view_token", "end"])
    async def test_a_session_of_someone_else_is_not_found(
        self,
        mocks: CollaboratorMocks[LiveSessionHandler],
        stored: LiveSession | None,
        operation: str,
    ) -> None:
        mocks.repo.get_live_session.return_value = stored
        handler = mocks.handler
        calls: dict[str, Callable[[], Awaitable[object]]] = {
            "get": lambda: handler.get_session(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
            ),
            "heartbeat": lambda: handler.record_heartbeat(
                USER_ID,
                ORGANIZATION_ID,
                ORBIT_ID,
                LIVE_SESSION_ID,
                LiveSessionHeartbeatIn(
                    connected=True, token_expires_at=datetime.now(UTC)
                ),
            ),
            "view_token": lambda: handler.issue_view_token(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
            ),
            "end": lambda: handler.end_session(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
            ),
        }

        with pytest.raises(NotFoundError):
            await calls[operation]()

        mocks.repo.record_heartbeat.assert_not_awaited()
        mocks.repo.end_live_session.assert_not_awaited()
        mocks.token_repo.issue_token.assert_not_awaited()

    async def test_end_session(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        ended = _session(ended_at=datetime.now(UTC))
        mocks.repo.get_live_session.return_value = _session()
        mocks.repo.end_live_session.return_value = ended

        result = await mocks.handler.end_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LIVE_SESSION_ID
        )

        assert result == ended
        assert result.status == LiveSessionStatus.ENDED
        mocks.repo.end_live_session.assert_awaited_once_with(LIVE_SESSION_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.DELETE, ORBIT_ID
        )

    async def test_start_in_an_orbit_without_a_relay_is_refused(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.orbit_repo.get_orbit_simple.return_value = _orbit(relay_id=None)

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.start_session(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
            )

        assert error.value.status_code == 409
        assert "assign a relay in orbit settings" in error.value.message
        mocks.repo.check_session_slot.assert_not_awaited()
        mocks.repo.create_live_session.assert_not_awaited()

    async def test_start_on_a_draining_relay_is_refused(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay(status=RelayStatus.DRAINING)

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.start_session(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
            )

        assert error.value.status_code == 409
        assert error.value.message == (
            "Relay 'lab' is draining and takes no new sessions"
        )
        mocks.repo.check_session_slot.assert_not_awaited()
        mocks.repo.create_live_session.assert_not_awaited()

    @pytest.mark.parametrize(
        "capabilities",
        [
            {},
            {"sessions": {"version": 2, "api_versions": [2]}},
            {"sessions": {"version": 1, "api_versions": [2]}},
            {"custom.replay": {"version": 1}},
        ],
    )
    async def test_start_on_a_relay_without_sessions_is_refused(
        self,
        mocks: CollaboratorMocks[LiveSessionHandler],
        capabilities: dict[str, dict[str, Any]],
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay(capabilities=capabilities)

        with pytest.raises(ApplicationError) as error:
            await mocks.handler.start_session(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
            )

        assert error.value.status_code == 409
        assert error.value.message == "Relay 'lab' does not support sessions"
        mocks.repo.check_session_slot.assert_not_awaited()
        mocks.repo.create_live_session.assert_not_awaited()

    async def test_start_on_a_managed_relay_counts_toward_the_managed_limit(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay(organization_id=None)
        mocks.repo.create_live_session.return_value = _session(last_heartbeat_ago=None)

        await mocks.handler.start_session(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
        )

        mocks.repo.check_session_slot.assert_awaited_once_with(
            ORGANIZATION_ID, OrganizationResource.MANAGED_RELAY_SESSIONS, None
        )
        assert mocks.repo.create_live_session.await_args is not None
        assert mocks.repo.create_live_session.await_args.args[2] == (
            OrganizationResource.MANAGED_RELAY_SESSIONS
        )

    async def test_start_replacing_a_session_frees_its_slot_and_ends_it_on_create(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.create_live_session.return_value = _session(last_heartbeat_ago=None)

        await mocks.handler.start_session(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LiveSessionStartIn(label="run"),
            replacing="oldsession01",
        )

        mocks.repo.check_session_slot.assert_awaited_once_with(
            ORGANIZATION_ID, OrganizationResource.OWN_RELAY_SESSIONS, "oldsession01"
        )
        assert mocks.repo.create_live_session.await_args is not None
        assert mocks.repo.create_live_session.await_args.args[3] == "oldsession01"

    async def test_start_at_the_limit_is_refused_before_anything_is_created(
        self, mocks: CollaboratorMocks[LiveSessionHandler]
    ) -> None:
        mocks.repo.check_session_slot.side_effect = OrganizationLimitReachedError(
            "Organization reached maximum number of sessions on its own relays"
        )

        with pytest.raises(OrganizationLimitReachedError):
            await mocks.handler.start_session(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, LiveSessionStartIn(label="run")
            )

        mocks.repo.create_live_session.assert_not_awaited()
