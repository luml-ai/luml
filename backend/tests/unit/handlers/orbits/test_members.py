import logging
from unittest.mock import Mock
from uuid import uuid7

import pytest
from luml.handlers.orbits import OrbitHandler
from luml.infra.exceptions import (
    DatabaseConstraintError,
    InsufficientPermissionsError,
    OrbitMemberAlreadyExistsError,
    OrbitMemberNotAllowedError,
    OrbitMemberNotFoundError,
)
from luml.models import OrganizationMemberOrm
from luml.schemas.orbit import (
    OrbitMember,
    OrbitMemberCreate,
    OrbitRole,
    UpdateOrbitMember,
)
from luml.schemas.organization import OrgRole
from luml.schemas.permissions import Action, Resource

from tests.support.ids import ORBIT_ID, ORGANIZATION_ID, USER_ID
from tests.support.mocks import CollaboratorMocks


class TestOrbitMembers:
    async def test_get_orbit_members_returns_members(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit_member: OrbitMember
    ) -> None:
        expected = [orbit_member]

        mocks.orbits_repository.get_orbit_members.return_value = expected

        result = await mocks.handler.get_orbit_members(
            expected[0].user.id, ORGANIZATION_ID, expected[0].orbit_id
        )

        assert result == expected
        mocks.orbits_repository.get_orbit_members.assert_awaited_once_with(
            expected[0].orbit_id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            expected[0].user.id,
            Resource.ORBIT_USER,
            Action.LIST,
            expected[0].orbit_id,
        )

    @pytest.mark.parametrize("email_fails", [False, True])
    async def test_create_orbit_member_returns_member_and_logs_email_failure(
        self,
        mocks: CollaboratorMocks[OrbitHandler],
        orbit_member: OrbitMember,
        caplog: pytest.LogCaptureFixture,
        email_fails: bool,
    ) -> None:
        expected = orbit_member

        create_member = OrbitMemberCreate(
            user_id=USER_ID,
            orbit_id=expected.orbit_id,
            role=expected.role,
        )

        mocks.user_repository.get_organization_member.return_value = (
            OrganizationMemberOrm(
                id=uuid7(),
                user_id=uuid7(),
                organization_id=ORGANIZATION_ID,
                role=OrgRole.OWNER,
            )
        )
        mocks.orbits_repository.create_orbit_member.return_value = expected
        mocks.orbits_repository.get_orbit_simple.return_value = Mock(
            bucket_secret_id=1, organization_id=ORGANIZATION_ID, name="name"
        )
        if email_fails:
            mocks.email_handler.send_added_to_orbit_email.side_effect = RuntimeError(
                "email rejected"
            )

        with caplog.at_level(logging.ERROR, logger="luml.handlers.orbits"):
            result = await mocks.handler.create_orbit_member(
                expected.user.id, ORGANIZATION_ID, create_member
            )

        assert result == expected
        mocks.orbits_repository.create_orbit_member.assert_awaited_once_with(
            create_member
        )
        mocks.email_handler.send_added_to_orbit_email.assert_called_once()
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            expected.user.id,
            Resource.ORBIT_USER,
            Action.CREATE,
            expected.orbit_id,
        )
        if email_fails:
            assert "Failed to send added-to-orbit email" in caplog.text

    async def test_create_orbit_member_raises_conflict_when_member_exists(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit_member: OrbitMember
    ) -> None:
        member = OrbitMemberCreate(
            user_id=orbit_member.user.id,
            orbit_id=orbit_member.orbit_id,
            role=orbit_member.role,
        )
        mocks.user_repository.get_organization_member.return_value = Mock()
        mocks.orbits_repository.create_orbit_member.side_effect = (
            DatabaseConstraintError()
        )

        with pytest.raises(OrbitMemberAlreadyExistsError) as error:
            await mocks.handler.create_orbit_member(USER_ID, ORGANIZATION_ID, member)

        assert error.value.status_code == 409
        mocks.orbits_repository.create_orbit_member.assert_awaited_once_with(member)

    async def test_update_orbit_member_returns_updated_member(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit_member: OrbitMember
    ) -> None:
        expected = orbit_member.model_copy()
        expected.role = OrbitRole.ADMIN

        update_member = UpdateOrbitMember(id=expected.id, role=OrbitRole.ADMIN)

        mocks.orbits_repository.get_orbit_member.return_value = orbit_member
        mocks.orbits_repository.update_orbit_member.return_value = expected

        result = await mocks.handler.update_orbit_member(
            USER_ID, ORGANIZATION_ID, expected.orbit_id, expected.id, update_member
        )

        assert result == expected
        mocks.orbits_repository.update_orbit_member.assert_awaited_once_with(
            expected.id, expected.orbit_id, update_member
        )
        mocks.orbits_repository.get_orbit_member.assert_awaited_once_with(
            expected.id, expected.orbit_id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ORBIT_USER,
            Action.UPDATE,
            expected.orbit_id,
        )

    async def test_update_orbit_member_raises_not_found_when_member_missing(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        update_member = UpdateOrbitMember(id=uuid7(), role=OrbitRole.ADMIN)

        mocks.orbits_repository.get_orbit_member.return_value = None

        with pytest.raises(
            OrbitMemberNotFoundError, match="Orbit member not found"
        ) as error:
            await mocks.handler.update_orbit_member(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, update_member.id, update_member
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.update_orbit_member.assert_not_awaited()

    async def test_delete_orbit_member_deletes_member(
        self, mocks: CollaboratorMocks[OrbitHandler], orbit_member: OrbitMember
    ) -> None:
        mocks.orbits_repository.get_orbit_member.return_value = orbit_member
        mocks.orbits_repository.delete_orbit_member.return_value = None

        await mocks.handler.delete_orbit_member(
            USER_ID, ORGANIZATION_ID, orbit_member.orbit_id, orbit_member.id
        )
        mocks.orbits_repository.delete_orbit_member.assert_awaited_once_with(
            orbit_member.id, orbit_member.orbit_id
        )
        mocks.orbits_repository.get_orbit_member.assert_awaited_once_with(
            orbit_member.id, orbit_member.orbit_id
        )
        mocks.permissions_handler.check_permissions.assert_awaited_once_with(
            ORGANIZATION_ID,
            USER_ID,
            Resource.ORBIT_USER,
            Action.DELETE,
            orbit_member.orbit_id,
        )

    async def test_delete_orbit_member_raises_not_found_when_member_missing(
        self, mocks: CollaboratorMocks[OrbitHandler]
    ) -> None:
        member_id = uuid7()
        mocks.orbits_repository.get_orbit_member.return_value = None

        with pytest.raises(OrbitMemberNotFoundError) as error:
            await mocks.handler.delete_orbit_member(
                USER_ID, ORGANIZATION_ID, ORBIT_ID, member_id
            )

        assert error.value.status_code == 404
        mocks.orbits_repository.get_orbit_member.assert_awaited_once_with(
            member_id, ORBIT_ID
        )
        mocks.orbits_repository.delete_orbit_member.assert_not_awaited()

    @pytest.mark.parametrize("action", ["update", "delete"])
    async def test_mutation_rejects_own_membership(
        self,
        mocks: CollaboratorMocks[OrbitHandler],
        orbit_member: OrbitMember,
        action: str,
    ) -> None:
        mocks.orbits_repository.get_orbit_member.return_value = orbit_member

        mutation = (
            mocks.handler.update_orbit_member(
                orbit_member.user.id,
                ORGANIZATION_ID,
                orbit_member.orbit_id,
                orbit_member.id,
                UpdateOrbitMember(id=uuid7(), role=OrbitRole.ADMIN),
            )
            if action == "update"
            else mocks.handler.delete_orbit_member(
                orbit_member.user.id,
                ORGANIZATION_ID,
                orbit_member.orbit_id,
                orbit_member.id,
            )
        )

        with pytest.raises(OrbitMemberNotAllowedError):
            await mutation

        mocks.orbits_repository.update_orbit_member.assert_not_awaited()
        mocks.orbits_repository.delete_orbit_member.assert_not_awaited()

    @pytest.mark.parametrize("action", ["update", "delete"])
    async def test_mutation_requires_permissions(
        self,
        mocks: CollaboratorMocks[OrbitHandler],
        orbit_member: OrbitMember,
        action: str,
    ) -> None:
        mocks.orbits_repository.get_orbit_member.return_value = orbit_member
        mocks.permissions_handler.check_permissions.side_effect = (
            InsufficientPermissionsError()
        )

        mutation = (
            mocks.handler.update_orbit_member(
                USER_ID,
                ORGANIZATION_ID,
                orbit_member.orbit_id,
                orbit_member.id,
                UpdateOrbitMember(id=orbit_member.id, role=OrbitRole.ADMIN),
            )
            if action == "update"
            else mocks.handler.delete_orbit_member(
                USER_ID, ORGANIZATION_ID, orbit_member.orbit_id, orbit_member.id
            )
        )

        with pytest.raises(InsufficientPermissionsError):
            await mutation

        mocks.orbits_repository.update_orbit_member.assert_not_awaited()
        mocks.orbits_repository.delete_orbit_member.assert_not_awaited()
