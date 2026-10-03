from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, call, patch
from uuid import UUID

import pytest
from luml.handlers.flows import FlowHandler
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

USER_ID = UUID("0199c337-09f1-7d8f-b0c4-b68349bbe24b")
ORGANIZATION_ID = UUID("0199c337-09f2-7af1-af5e-83fd7a5b51a0")
ORBIT_ID = UUID("0199c337-09f3-753e-9def-b27745e69be6")
FLOW_ID = UUID("0199c337-09f6-7a3b-8c1d-2e3f4a5b6c7d")
OLD_SESSION_ID = "oldsession01"
NEW_SESSION_ID = "newsession01"

REPO = "luml.handlers.flows.FlowRepository"
SESSIONS = "luml.handlers.flows.LiveSessionHandler"
CHECK_PERMISSIONS = "luml.handlers.flows.PermissionsHandler.check_permissions"


def _handler() -> FlowHandler:
    return FlowHandler(
        config.model_copy(update={"APP_EMAIL_URL": "https://app.luml.ai/"})
    )


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
        public_url=f"https://{NEW_SESSION_ID}.tunnel.example",
        agent_url="wss://tunnel.example/connect",
        expose_token="opaque",
        token_expires_at=datetime.now(UTC),
    )


@pytest.fixture
def check_permissions() -> Iterator[AsyncMock]:
    with patch(CHECK_PERMISSIONS, new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mocks() -> Iterator[dict[str, AsyncMock]]:
    targets = {
        "delete_gone_flows": f"{REPO}.delete_gone_flows",
        "get_flow_by_name": f"{REPO}.get_flow_by_name",
        "attach_session": f"{REPO}.attach_session",
        "list_flows": f"{REPO}.list_flows",
        "get_flow": f"{REPO}.get_flow",
        "delete_flow": f"{REPO}.delete_flow",
        "start_session": f"{SESSIONS}.start_session",
        "end_session": f"{SESSIONS}.end_session",
    }
    patches = {
        name: patch(target, new_callable=AsyncMock) for name, target in targets.items()
    }
    started = {name: p.start() for name, p in patches.items()}
    started["get_flow_by_name"].return_value = None
    started["start_session"].return_value = _started()
    started["attach_session"].return_value = (_flow(NEW_SESSION_ID), None)
    yield started
    for p in patches.values():
        p.stop()


async def _expose() -> FlowExposeOut:
    return await _handler().expose_flow(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, FlowExposeIn(name="training")
    )


@pytest.mark.asyncio
async def test_a_flow_is_exposed(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    result = await _expose()

    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.CREATE, ORBIT_ID
    )
    mocks["delete_gone_flows"].assert_awaited_once()
    mocks["get_flow_by_name"].assert_awaited_once_with(ORBIT_ID, USER_ID, "training")
    mocks["start_session"].assert_awaited_once_with(
        USER_ID,
        ORGANIZATION_ID,
        ORBIT_ID,
        LiveSessionStartIn(label="training"),
        replacing=None,
    )
    mocks["attach_session"].assert_awaited_once_with(
        FlowCreate(
            orbit_id=ORBIT_ID,
            user_id=USER_ID,
            name="training",
            session_id=NEW_SESSION_ID,
        )
    )
    mocks["end_session"].assert_not_awaited()
    assert result.flow == mocks["attach_session"].return_value[0]
    assert result.session == mocks["start_session"].return_value
    assert result.app_url == (
        f"https://app.luml.ai/organization/{ORGANIZATION_ID}/orbit/{ORBIT_ID}/flow"
    )


@pytest.mark.asyncio
async def test_gone_flows_are_deleted_before_the_name_is_looked_up(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    order: list[str] = []
    mocks["delete_gone_flows"].side_effect = lambda: order.append("delete")
    mocks["get_flow_by_name"].side_effect = lambda *args: order.append("find")

    await _expose()

    assert order == ["delete", "find"]


@pytest.mark.asyncio
async def test_re_exposing_replaces_the_flows_session(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    mocks["get_flow_by_name"].return_value = _flow(OLD_SESSION_ID)
    mocks["attach_session"].return_value = (_flow(NEW_SESSION_ID), OLD_SESSION_ID)

    result = await _expose()

    assert mocks["start_session"].await_args is not None
    assert mocks["start_session"].await_args.kwargs == {"replacing": OLD_SESSION_ID}
    # The start already ended the replaced session together with the insert.
    mocks["end_session"].assert_not_awaited()
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
@pytest.mark.asyncio
async def test_a_refused_expose_ends_nothing_and_creates_nothing(
    check_permissions: AsyncMock,
    mocks: dict[str, AsyncMock],
    refusal: ApplicationError,
    existing: bool,
) -> None:
    if existing:
        mocks["get_flow_by_name"].return_value = _flow(OLD_SESSION_ID)
    mocks["start_session"].side_effect = refusal

    with pytest.raises(type(refusal)) as error:
        await _expose()

    assert error.value is refusal
    mocks["attach_session"].assert_not_awaited()
    mocks["end_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_losing_a_concurrent_expose_ends_the_winners_session(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    mocks["attach_session"].return_value = (_flow(NEW_SESSION_ID), "winnersession")

    await _expose()

    mocks["end_session"].assert_awaited_once_with(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, "winnersession"
    )


@pytest.mark.asyncio
async def test_someone_outside_the_orbit_cannot_expose(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    check_permissions.side_effect = InsufficientPermissionsError()

    with pytest.raises(InsufficientPermissionsError):
        await _expose()

    mocks["delete_gone_flows"].assert_not_awaited()
    mocks["start_session"].assert_not_awaited()


@pytest.mark.asyncio
async def test_list_asks_for_the_callers_visible_flows(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    mocks["list_flows"].return_value = [_flow()]

    result = await _handler().list_flows(USER_ID, ORGANIZATION_ID, ORBIT_ID)

    assert result == mocks["list_flows"].return_value
    mocks["list_flows"].assert_awaited_once_with(ORBIT_ID, USER_ID)
    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.LIST, ORBIT_ID
    )
    mocks["delete_gone_flows"].assert_not_awaited()


@pytest.mark.asyncio
async def test_read_a_flow(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    mocks["get_flow"].return_value = _flow()

    result = await _handler().get_flow(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

    assert result == mocks["get_flow"].return_value
    mocks["get_flow"].assert_awaited_once_with(ORBIT_ID, FLOW_ID, USER_ID)
    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.READ, ORBIT_ID
    )


@pytest.mark.asyncio
async def test_removing_a_flow_ends_its_session_then_deletes_it(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    mocks["get_flow"].return_value = _flow()
    order: list[str] = []
    mocks["delete_gone_flows"].side_effect = lambda: order.append("delete gone")
    mocks["end_session"].side_effect = lambda *args: order.append("end")
    mocks["delete_flow"].side_effect = lambda *args: order.append("delete")

    await _handler().remove_flow(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

    check_permissions.assert_awaited_once_with(
        ORGANIZATION_ID, USER_ID, Resource.LIVE_SESSION, Action.DELETE, ORBIT_ID
    )
    assert order == ["delete gone", "end", "delete"]
    assert mocks["end_session"].await_args == call(
        USER_ID, ORGANIZATION_ID, ORBIT_ID, OLD_SESSION_ID
    )
    mocks["delete_flow"].assert_awaited_once_with(FLOW_ID)


@pytest.mark.parametrize("operation", ["get", "remove"])
@pytest.mark.asyncio
async def test_a_flow_the_caller_may_not_see_is_not_found(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock], operation: str
) -> None:
    mocks["get_flow"].return_value = None
    handler = _handler()
    method = handler.get_flow if operation == "get" else handler.remove_flow

    with pytest.raises(NotFoundError, match="Flow not found"):
        await method(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

    mocks["end_session"].assert_not_awaited()
    mocks["delete_flow"].assert_not_awaited()


@pytest.mark.asyncio
async def test_removal_by_someone_other_than_the_session_owner_deletes_nothing(
    check_permissions: AsyncMock, mocks: dict[str, AsyncMock]
) -> None:
    mocks["get_flow"].return_value = _flow()
    mocks["end_session"].side_effect = NotFoundError("Live session not found")

    with pytest.raises(NotFoundError):
        await _handler().remove_flow(USER_ID, ORGANIZATION_ID, ORBIT_ID, FLOW_ID)

    mocks["delete_flow"].assert_not_awaited()
