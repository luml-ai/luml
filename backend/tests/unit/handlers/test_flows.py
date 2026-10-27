from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest
from luml.handlers.flows import FlowHandler
from luml.handlers.live_sessions import LiveSessionHandler
from luml.infra.exceptions import (
    ApplicationError,
    InsufficientPermissionsError,
    NotFoundError,
    OrganizationLimitReachedError,
)
from luml.schemas.flow import (
    Flow,
    FlowCreate,
    FlowExposeIn,
    FlowExposeOut,
    FlowSession,
)
from luml.schemas.live_session import (
    LiveSessionStartIn,
    LiveSessionStartOut,
    LiveSessionStatus,
)
from luml.schemas.permissions import Action, Resource
from luml.settings import config

from tests.support.ids import FLOW_ID, ORBIT_ID, ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators

OLD_SESSION_ID = "oldsession01"
NEW_SESSION_ID = "newsession01"


def _flow(session_id: str = OLD_SESSION_ID) -> Flow:
    return Flow(
        id=FLOW_ID,
        orbit_id=ORBIT_ID,
        user_id=USER_ID,
        name="training",
        session=FlowSession(
            id=session_id,
            status=LiveSessionStatus.LIVE,
            started_at=datetime.now(UTC),
            last_heartbeat_at=datetime.now(UTC),
        ),
        created_at=datetime.now(UTC),
    )


def _started() -> LiveSessionStartOut:
    return LiveSessionStartOut(
        id=NEW_SESSION_ID,
        public_url=f"https://{NEW_SESSION_ID}.sessions.example",
        agent_url="wss://sessions.example/connect",
        expose_token="opaque",
        token_expires_at=datetime.now(UTC),
    )


@pytest.fixture
def mocks() -> CollaboratorMocks[FlowHandler]:
    handler = FlowHandler(
        config.model_copy(update={"APP_EMAIL_URL": "https://app.luml.ai/"})
    )
    mocks = mock_collaborators(handler)
    mocks.live_sessions = Mock(spec=LiveSessionHandler)
    handler._live_sessions = mocks.live_sessions
    mocks.repo.get_flow_by_name.return_value = None
    mocks.repo.attach_session.return_value = (_flow(NEW_SESSION_ID), None)
    mocks.live_sessions.start_session.return_value = _started()
    mocks.live_sessions.end_session.return_value = None
    return mocks


async def _expose(mocks: CollaboratorMocks[FlowHandler]) -> FlowExposeOut:
    return await mocks.handler.expose_flow(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, FlowExposeIn(name="training")
    )


class TestFlowHandler:
    async def test_a_flow_is_exposed(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        result = await _expose(mocks)

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.CREATE, ORBIT_ID
        )
        mocks.repo.delete_gone_flows.assert_awaited_once()
        mocks.repo.get_flow_by_name.assert_awaited_once_with(
            ORBIT_ID, USER_ID, "training"
        )
        mocks.live_sessions.start_session.assert_awaited_once_with(
            USER_ID,
            ORGANIZATION_ID,
            ORBIT_ID,
            LiveSessionStartIn(label="training"),
            replacing=None,
        )
        mocks.repo.attach_session.assert_awaited_once_with(
            FlowCreate(
                orbit_id=ORBIT_ID,
                user_id=USER_ID,
                name="training",
                session_id=NEW_SESSION_ID,
            )
        )
        mocks.live_sessions.end_session.assert_not_awaited()
        assert result.flow == mocks.repo.attach_session.return_value[0]
        assert result.session == mocks.live_sessions.start_session.return_value
        assert result.app_url == (
            f"https://app.luml.ai/organization/{ORGANIZATION_ID}/orbit/{ORBIT_ID}/flow"
        )

    async def test_gone_flows_are_deleted_before_the_name_is_looked_up(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        order: list[str] = []
        mocks.repo.delete_gone_flows.side_effect = lambda: order.append("delete")
        mocks.repo.get_flow_by_name.side_effect = lambda *args: order.append("find")

        await _expose(mocks)

        assert order == ["delete", "find"]

    async def test_re_exposing_replaces_the_flows_session(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        mocks.repo.get_flow_by_name.return_value = _flow(OLD_SESSION_ID)
        mocks.repo.attach_session.return_value = (
            _flow(NEW_SESSION_ID),
            OLD_SESSION_ID,
        )

        result = await _expose(mocks)

        assert mocks.live_sessions.start_session.await_args is not None
        assert mocks.live_sessions.start_session.await_args.kwargs == {
            "replacing": OLD_SESSION_ID
        }
        mocks.live_sessions.end_session.assert_not_awaited()
        assert result.flow.id == FLOW_ID
        assert result.flow.session.id == NEW_SESSION_ID

    @pytest.mark.parametrize(
        "refusal",
        [
            OrganizationLimitReachedError(
                "Organization reached maximum number of sessions on its own relays"
            ),
            ApplicationError("Relay 'lab' is draining and takes no new sessions", 409),
            ApplicationError(
                "The orbit has no relay; assign a relay in orbit settings", 409
            ),
        ],
        ids=["limit", "draining", "no-relay"],
    )
    @pytest.mark.parametrize("existing", [False, True], ids=["new-name", "re-expose"])
    async def test_a_refused_expose_ends_nothing_and_creates_nothing(
        self,
        mocks: CollaboratorMocks[FlowHandler],
        refusal: ApplicationError,
        existing: bool,
    ) -> None:
        if existing:
            mocks.repo.get_flow_by_name.return_value = _flow(OLD_SESSION_ID)
        mocks.live_sessions.start_session.side_effect = refusal

        with pytest.raises(type(refusal)) as error:
            await _expose(mocks)

        assert error.value is refusal
        mocks.repo.attach_session.assert_not_awaited()
        mocks.live_sessions.end_session.assert_not_awaited()

    async def test_losing_a_concurrent_expose_ends_the_winners_session(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        mocks.repo.attach_session.return_value = (
            _flow(NEW_SESSION_ID),
            "winnersession",
        )

        await _expose(mocks)

        mocks.live_sessions.end_session.assert_awaited_once_with(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, "winnersession"
        )

    async def test_someone_outside_the_orbit_cannot_expose(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        with pytest.raises(InsufficientPermissionsError):
            await _expose(mocks)

        mocks.repo.delete_gone_flows.assert_not_awaited()
        mocks.live_sessions.start_session.assert_not_awaited()

    async def test_list_asks_for_the_callers_visible_flows(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        mocks.repo.list_flows.return_value = [_flow()]

        result = await mocks.handler.list_flows(USER_ID, ORGANIZATION_ID, ORBIT_ID)

        assert result == mocks.repo.list_flows.return_value
        mocks.repo.list_flows.assert_awaited_once_with(ORBIT_ID, USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.LIST, ORBIT_ID
        )
        mocks.repo.delete_gone_flows.assert_not_awaited()

    async def test_read_a_flow(self, mocks: CollaboratorMocks[FlowHandler]) -> None:
        mocks.repo.get_flow.return_value = _flow()

        result = await mocks.handler.get_flow(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID
        )

        assert result == mocks.repo.get_flow.return_value
        mocks.repo.get_flow.assert_awaited_once_with(ORBIT_ID, FLOW_ID, USER_ID)
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.READ, ORBIT_ID
        )

    async def test_removing_a_flow_ends_its_session_then_deletes_it(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        mocks.repo.get_flow.return_value = _flow()
        order: list[str] = []
        mocks.repo.delete_gone_flows.side_effect = lambda: order.append("delete gone")
        mocks.live_sessions.end_session.side_effect = lambda *args: order.append("end")
        mocks.repo.delete_flow.side_effect = lambda *args: order.append("delete")

        await mocks.handler.remove_flow(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.DELETE, ORBIT_ID
        )
        assert order == ["delete gone", "end", "delete"]
        assert mocks.live_sessions.end_session.await_args == call(
            USER_ID, ORGANIZATION_ID, ORBIT_ID, OLD_SESSION_ID
        )
        mocks.repo.delete_flow.assert_awaited_once_with(FLOW_ID, OLD_SESSION_ID)

    @pytest.mark.parametrize("operation", ["get", "remove"])
    async def test_a_flow_the_caller_may_not_see_is_not_found(
        self, mocks: CollaboratorMocks[FlowHandler], operation: str
    ) -> None:
        mocks.repo.get_flow.return_value = None
        handler = mocks.handler
        method = handler.get_flow if operation == "get" else handler.remove_flow

        with pytest.raises(NotFoundError, match="Flow not found"):
            await method(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

        mocks.live_sessions.end_session.assert_not_awaited()
        mocks.repo.delete_flow.assert_not_awaited()

    async def test_removal_by_someone_other_than_the_session_owner_deletes_nothing(
        self, mocks: CollaboratorMocks[FlowHandler]
    ) -> None:
        mocks.repo.get_flow.return_value = _flow()
        mocks.live_sessions.end_session.side_effect = NotFoundError(
            "Live session not found"
        )

        with pytest.raises(NotFoundError):
            await mocks.handler.remove_flow(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

        mocks.repo.delete_flow.assert_not_awaited()
