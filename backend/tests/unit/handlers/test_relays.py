from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from luml.handlers.relays import RelayHandler
from luml.infra.exceptions import (
    ApplicationError,
    DatabaseConstraintError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.relay import (
    Relay,
    RelayCreate,
    RelayCreateIn,
    RelayKind,
    RelayStatus,
    RelayUpdateIn,
)
from luml.settings import config
from pydantic import ValidationError

from tests.support.ids import ORGANIZATION_ID, RELAY_ID, USER_ID
from tests.support.mocks import CollaboratorMocks, mock_collaborators


@pytest.fixture
def mocks() -> CollaboratorMocks[RelayHandler]:
    return mock_collaborators(RelayHandler())


def _relay(organization_id: UUID | None = ORGANIZATION_ID) -> Relay:
    return Relay(
        id=RELAY_ID,
        organization_id=organization_id,
        label="lab",
        base_domain="sessions.example",
        agent_url="wss://relay.sessions.example/connect",
        status=RelayStatus.ENABLED,
        created_at=datetime.now(UTC),
    )


def _create_in() -> RelayCreateIn:
    return RelayCreateIn(
        label="lab",
        base_domain="sessions.example",
        agent_url="wss://relay.sessions.example/connect",
    )


class TestRelayHandler:
    async def test_create_relay_stores_the_hash_and_answers_the_token_once(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.create_relay.return_value = _relay()

        created = await mocks.handler.create_relay(
            USER_ID, ORGANIZATION_ID, _create_in()
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.CREATE
        )
        assert mocks.relay_repo.create_relay.await_args is not None
        stored: RelayCreate = mocks.relay_repo.create_relay.await_args.args[0]
        assert created.token.startswith("dfsrelay_")
        assert stored.organization_id == ORGANIZATION_ID
        assert stored.token_hash == mocks.handler.hash_token(created.token)
        assert stored.token_hash != created.token
        assert created.relay.kind == RelayKind.OWN
        assert "token_hash" not in created.relay.model_dump()

    async def test_create_relay_refuses_a_taken_base_domain_with_a_conflict(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.create_relay.side_effect = DatabaseConstraintError()

        with pytest.raises(ApplicationError) as refusal:
            await mocks.handler.create_relay(USER_ID, ORGANIZATION_ID, _create_in())

        assert refusal.value.status_code == 409
        assert "base domain" in refusal.value.message

    async def test_create_relay_without_permission_creates_nothing(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        with pytest.raises(InsufficientPermissionsError):
            await mocks.handler.create_relay(USER_ID, ORGANIZATION_ID, _create_in())

        mocks.relay_repo.create_relay.assert_not_awaited()

    async def test_list_relays_includes_managed_ones(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.list_usable_relays.return_value = [
            _relay(),
            _relay(organization_id=None),
        ]

        relays = await mocks.handler.list_relays(USER_ID, ORGANIZATION_ID)

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.LIST
        )
        mocks.relay_repo.list_usable_relays.assert_awaited_once_with(ORGANIZATION_ID)
        assert [relay.kind for relay in relays] == [RelayKind.OWN, RelayKind.MANAGED]

    async def test_get_relay_of_another_organization_is_not_found(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = None

        with pytest.raises(NotFoundError):
            await mocks.handler.get_relay(USER_ID, ORGANIZATION_ID, RELAY_ID)

        mocks.relay_repo.get_relay.assert_awaited_once_with(RELAY_ID, ORGANIZATION_ID)

    async def test_update_relay_changes_own_relay(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay()
        mocks.relay_repo.update_relay.return_value = _relay().model_copy(
            update={"status": RelayStatus.DRAINING}
        )
        change = RelayUpdateIn(status=RelayStatus.DRAINING)

        updated = await mocks.handler.update_relay(
            USER_ID, ORGANIZATION_ID, RELAY_ID, change
        )

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.UPDATE
        )
        mocks.relay_repo.update_relay.assert_awaited_once_with(RELAY_ID, change)
        assert updated.status == RelayStatus.DRAINING

    async def test_update_relay_to_a_taken_base_domain_is_a_conflict(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay()
        mocks.relay_repo.update_relay.side_effect = DatabaseConstraintError()

        with pytest.raises(ApplicationError) as refusal:
            await mocks.handler.update_relay(
                USER_ID,
                ORGANIZATION_ID,
                RELAY_ID,
                RelayUpdateIn(base_domain="taken.example"),
            )

        assert refusal.value.status_code == 409

    async def test_rotate_token_keeps_the_old_token_for_the_overlap(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay()
        mocks.relay_repo.rotate_token.return_value = _relay()
        before = datetime.now(UTC)

        rotated = await mocks.handler.rotate_token(USER_ID, ORGANIZATION_ID, RELAY_ID)

        assert mocks.relay_repo.rotate_token.await_args is not None
        relay_id, token_hash, overlap_end = (
            mocks.relay_repo.rotate_token.await_args.args
        )
        overlap = timedelta(seconds=config.LIVE_SESSION_RELAY_TOKEN_OVERLAP_SECONDS)
        assert relay_id == RELAY_ID
        assert rotated.token.startswith("dfsrelay_")
        assert token_hash == mocks.handler.hash_token(rotated.token)
        assert before + overlap <= overlap_end <= datetime.now(UTC) + overlap

    async def test_delete_relay_removes_own_relay(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay()
        mocks.relay_repo.delete_relay.return_value = True

        await mocks.handler.delete_relay(USER_ID, ORGANIZATION_ID, RELAY_ID)

        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID, USER_ID, Resource.RELAY, Action.DELETE
        )
        mocks.relay_repo.delete_relay.assert_awaited_once_with(RELAY_ID)

    async def test_managed_relay_is_read_only(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay.return_value = _relay(organization_id=None)

        for attempt in (
            mocks.handler.update_relay(
                USER_ID, ORGANIZATION_ID, RELAY_ID, RelayUpdateIn(label="mine")
            ),
            mocks.handler.rotate_token(USER_ID, ORGANIZATION_ID, RELAY_ID),
            mocks.handler.delete_relay(USER_ID, ORGANIZATION_ID, RELAY_ID),
        ):
            with pytest.raises(ApplicationError, match="Managed relays are read-only"):
                await attempt

        mocks.relay_repo.update_relay.assert_not_awaited()
        mocks.relay_repo.rotate_token.assert_not_awaited()
        mocks.relay_repo.delete_relay.assert_not_awaited()

    async def test_authenticate_token_looks_up_by_hash(
        self, mocks: CollaboratorMocks[RelayHandler]
    ) -> None:
        mocks.relay_repo.get_relay_by_token_hash.return_value = _relay()

        relay = await mocks.handler.authenticate_token("dfsrelay_secret")

        mocks.relay_repo.get_relay_by_token_hash.assert_awaited_once_with(
            mocks.handler.hash_token("dfsrelay_secret")
        )
        assert relay is not None

    @pytest.mark.parametrize(
        ("base_domain", "problem"),
        [
            ("https://sessions.example", "scheme"),
            ("sessions.example:8443", "port"),
            ("sessions.example/path", "path"),
            ("sessions.example.", "dot"),
            ("sessions_example", "bare hostname"),
            ("", "bare hostname"),
        ],
    )
    def test_base_domain_must_be_a_bare_hostname(
        self, base_domain: str, problem: str
    ) -> None:
        with pytest.raises(ValidationError, match=problem):
            RelayCreateIn(
                label="lab", base_domain=base_domain, agent_url="ws://relay.example"
            )

    def test_base_domain_is_stored_lower_case(self) -> None:
        relay = RelayCreateIn(
            label="lab", base_domain="Sessions.Example", agent_url="ws://relay.example"
        )

        assert relay.base_domain == "sessions.example"

    @pytest.mark.parametrize(
        "agent_url",
        ["https://relay.example/connect", "relay.example:8080", "ws://", "ftp://relay"],
    )
    def test_agent_address_must_be_a_ws_or_wss_address(self, agent_url: str) -> None:
        with pytest.raises(ValidationError, match="ws or wss"):
            RelayCreateIn(
                label="lab", base_domain="sessions.example", agent_url=agent_url
            )

    @pytest.mark.parametrize(
        "agent_url",
        ["wss://relay.example:99999/connect", "ws://relay.example:port/connect"],
    )
    def test_agent_address_must_have_a_valid_port(self, agent_url: str) -> None:
        with pytest.raises(ValidationError, match="invalid port"):
            RelayCreateIn(
                label="lab", base_domain="sessions.example", agent_url=agent_url
            )

    def test_update_validates_only_the_given_fields(self) -> None:
        with pytest.raises(ValidationError, match="port"):
            RelayUpdateIn(base_domain="sessions.example:80")

        assert RelayUpdateIn(label="new").model_dump(exclude_unset=True) == {
            "label": "new"
        }

    @pytest.mark.parametrize(
        ("last_seen_ago", "online"),
        [(None, False), (timedelta(minutes=4), True), (timedelta(minutes=6), False)],
    )
    def test_relay_is_online_while_its_last_report_is_recent(
        self, last_seen_ago: timedelta | None, online: bool
    ) -> None:
        last_seen_at = (
            None if last_seen_ago is None else datetime.now(UTC) - last_seen_ago
        )

        relay = _relay().model_copy(update={"last_seen_at": last_seen_at})

        assert relay.online is online
